"""独立CPU数据操作进程；可用 python -m model_platform.operations_runner 启动。"""
from contextlib import contextmanager
import logging
import os
import time

from sqlalchemy import select, update

from .config import Settings
from .data_models import DataOperation
from .database import make_engine, make_session_factory
from .errors import Problem
from .models import User
from .permissions import workspace_access
from .services.common import commit
from .services.data_processors import process_data
from .services.data_samples import read_source, source
from .services.dataset_files import controlled_path, parse_samples
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
            changed = db.execute(update(DataOperation).where(DataOperation.id == operation_id,
                DataOperation.status == "running").values(status="review", candidates=candidates,
                progress={"phase": "待发布", "done": len(rows), "total": len(rows)}, revision=DataOperation.revision + 1))
            commit(db)
            if changed.rowcount != 1:
                raise Cancelled()
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


def main():
    settings = Settings()
    engine = make_engine(settings.db_url)
    sessions = make_session_factory(engine)
    try:
        with exclusive_runner(settings):
            recover_interrupted(sessions)
            while True:
                if not run_one(sessions, settings):
                    time.sleep(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
