"""独立CPU数据操作进程；可用 python -m model_platform.operations_runner 启动。"""
from contextlib import contextmanager
import asyncio
import logging
import os
import time

from sqlalchemy import select, update

from .assistant_models import AssistantRequest
from .config import Settings
from .data_models import DataOperation
from .database import aware, make_engine, make_session_factory, utcnow
from .errors import Problem
from .models import User
from .permissions import workspace_access
from .services.assistant_outputs import normalize
from .services.assistant_requests import revalidate
from .services.common import commit
from .services.data_processors import process_data
from .services.data_samples import read_source, source
from .services.dataset_files import controlled_path, parse_samples
from .services.model_connections import completion
from .services.platform_settings import dataset_limits


class Cancelled(Exception):
    pass


@contextmanager
def exclusive_runner(settings):
    path = settings.runtime_dir / "operations.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
                stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def recover_interrupted(sessions):
    # 仅在已取得进程独占锁后调用；待审核结果不受影响。
    with sessions() as db:
        db.execute(update(DataOperation).where(DataOperation.status == "running").values(
            status="failed", error="数据处理进程中断，请重新创建任务", revision=DataOperation.revision + 1))
        db.execute(update(AssistantRequest).where(AssistantRequest.status == "running").values(
            status="failed", error={"code": "INTERRUPTED", "message": "调用进程中断，请重新生成预览确认"},
            revision=AssistantRequest.revision + 1))
        commit(db)


def run_one(sessions, settings):
    with sessions() as db:
        item = db.scalar(select(DataOperation).where(DataOperation.status == "queued")
                         .order_by(DataOperation.created_at, DataOperation.id).limit(1))
        if item is None:
            return False
        operation_id = item.id
        claimed = db.execute(update(DataOperation).where(DataOperation.id == operation_id,
            DataOperation.status == "queued").values(status="running", progress={"phase": "读取数据", "done": 0},
            revision=DataOperation.revision + 1))
        commit(db)
        if claimed.rowcount != 1:
            return True
    owned_paths = []

    def check(done, total):
        if done % 16 and done != total:
            return
        with sessions() as db:
            changed = db.execute(update(DataOperation).where(DataOperation.id == operation_id,
                DataOperation.status == "running").values(progress={"phase": "处理样本", "done": done, "total": total}))
            commit(db)
            if changed.rowcount != 1:
                raise Cancelled()

    try:
        with sessions() as db:
            item = db.get(DataOperation, operation_id)
            actor = db.get(User, item.created_by)
            if not actor or not actor.active:
                raise Problem(403, "FORBIDDEN", "创建账号已停用")
            workspace_access(db, actor, item.workspace_id, "datasets.write")
            dataset, version = source(db, item.workspace_id, item.version_id)
            from .services.asset_lifecycle import ensure_active
            ensure_active(dataset)
            rows, content = read_source(settings, dataset, version)
            limits = dataset_limits(db, settings)
            task_type, kind, options, workspace_id = dataset.task_type, item.kind, dict(item.options), item.workspace_id
        outputs = process_data(task_type, rows, content, kind, options, check, limits.max_samples)
        candidates = []
        for partition, filename, output in outputs:
            check(len(rows), len(rows))
            if len(output) > limits.max_upload_bytes:
                raise Problem(413, "FILE_TOO_LARGE", "处理结果超过文件上限")
            _, metadata = parse_samples(output, task_type, filename, limits.max_samples)
            key = f"{workspace_id}/operations/{operation_id}/{partition}.{metadata['format']}"
            path = controlled_path(settings, key)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                owned_paths.append(path)
                stream.write(output)
            candidates.append({"partition": partition, "filename": f"{partition}-{filename}", "storage_key": key, **metadata})
        with sessions() as db:
            item = db.get(DataOperation, operation_id)
            actor = db.get(User, item.created_by)
            if not actor or not actor.active:
                raise Problem(403, 'FORBIDDEN', '创建账号已停用')
            workspace_access(db, actor, item.workspace_id, 'datasets.write')
            dataset, _ = source(db, item.workspace_id, item.version_id)
            ensure_active(dataset)
            from .services.budgets import charge_objects
            charge_objects(db, actor, [{'id': f'candidate:{operation_id}:{index}',
                'workspace_id': workspace_id, 'kind': 'candidate', 'object_id': operation_id,
                'storage_key': item['storage_key'], 'size_bytes': item['size_bytes']}
                for index, item in enumerate(candidates)])
            changed = db.execute(update(DataOperation).where(DataOperation.id == operation_id,
                DataOperation.status == "running").values(status="review", candidates=candidates,
                progress={"phase": "待发布", "done": len(rows), "total": len(rows)}, revision=DataOperation.revision + 1))
            if changed.rowcount != 1:
                raise Cancelled()
            commit(db)
        return True
    except Exception as error:
        with sessions() as db:
            db.execute(update(DataOperation).where(DataOperation.id == operation_id,
                DataOperation.status == "running").values(status="failed",
                error=error.message[:400] if isinstance(error, Problem) else "数据处理失败，请检查任务和文件限制",
                revision=DataOperation.revision + 1))
            commit(db)
        for path in owned_paths:
            path.unlink(missing_ok=True)
        if not isinstance(error, (Cancelled, Problem)):
            logging.error("data_operation_failed id=%s type=%s", operation_id, type(error).__name__)
        return True


def run_assistant(sessions, settings):
    """执行一次已确认的智能请求；每轮只取一条，失败保留记录不自动重试。"""
    with sessions() as db:
        item = db.scalar(select(AssistantRequest).where(AssistantRequest.status == "queued")
                         .order_by(AssistantRequest.confirmed_at, AssistantRequest.id).limit(1))
        if item is None:
            return False
        request_id = item.id
        claimed = db.execute(update(AssistantRequest).where(AssistantRequest.id == request_id,
            AssistantRequest.status == "queued").values(status="running", revision=AssistantRequest.revision + 1))
        commit(db)
        if claimed.rowcount != 1:
            return True
        try:
            actor = db.get(User, item.created_by)
            if not actor or not actor.active:
                raise Problem(403, "FORBIDDEN", "创建账号已停用")
            if aware(item.expires_at) <= utcnow():
                raise Problem(409, "PREVIEW_STALE", "预览已过期，请重新生成")
            # 执行前复核空间授权与连接，策略或连接已停用时不再外发。
            _, connection = revalidate(db, actor, item, settings)
            messages, max_tokens, purpose, binding = item.messages, item.max_tokens, item.purpose, item.source
        except Problem as error:
            failed(sessions, request_id, error)
            return True
        usage = {}
        try:
            text, usage = asyncio.run(completion(settings, connection, messages, max_tokens=max_tokens))
            result = normalize(purpose, text, binding)
        except Problem as error:
            failed(sessions, request_id, error, usage=usage)
            return True
        except Exception as error:
            logging.error("assistant_failed id=%s type=%s", request_id, type(error).__name__)
            failed(sessions, request_id, Problem(502, "PROVIDER_ERROR", "调用模型失败，请重新生成"))
            return True
        with sessions() as db:
            # 期间被取消时状态已不是running，保留取消结果。
            db.execute(update(AssistantRequest).where(AssistantRequest.id == request_id,
                AssistantRequest.status == "running").values(status="succeeded", result=result,
                usage=counted_usage(usage), revision=AssistantRequest.revision + 1))
            commit(db)
        return True


def counted_usage(usage):
    """只保留供应商实际报告的非负整数用量，不推算费用。"""
    if not isinstance(usage, dict):
        return {}
    return {key: value for key, value in usage.items()
            if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
            and type(value) is int and value >= 0}


def failed(sessions, request_id, error, *, usage=None):
    with sessions() as db:
        db.execute(update(AssistantRequest).where(AssistantRequest.id == request_id,
            AssistantRequest.status == "running").values(status="failed", revision=AssistantRequest.revision + 1,
            error={"code": error.code, "message": error.message}, usage=counted_usage(usage)))
        commit(db)


def main():
    settings = Settings()
    engine = make_engine(settings.db_url)
    sessions = make_session_factory(engine)
    try:
        with exclusive_runner(settings):
            recover_interrupted(sessions)
            while True:
                # 两类队列各执行一次，避免某一类长期占满进程。
                busy = run_one(sessions, settings)
                busy = run_assistant(sessions, settings) or busy
                if not busy:
                    time.sleep(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
