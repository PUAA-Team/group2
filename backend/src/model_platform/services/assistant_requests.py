"""智能辅助请求：服务端预览、确认入队、取消与人工采纳。"""
from datetime import timedelta
import hashlib
import json

from sqlalchemy import func, select, update

from ..assistant_models import AssistantAdoption, AssistantRequest, WorkspaceAIPolicy
from ..assistant_schemas import AssistantPrepare
from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..job_models import Job
from ..job_schemas import JobInput, TrainConfig
from ..models import Workspace
from ..data_models import AnnotationResult
from ..permissions import workspace_access
from .annotations import apply_candidates, find_batch
from .assistant_policy import policy_view, usable_connection
from .assistant_sources import build_messages, collect_source, permission
from .data_samples import source, read_source
from .common import audit, commit, serialize
from .jobs import inputs


def find_request(db, workspace_id, request_id):
    item = db.scalar(select(AssistantRequest).where(AssistantRequest.id == request_id,
        AssistantRequest.workspace_id == workspace_id))
    if item is None:
        raise Problem(404, "NOT_FOUND", "智能请求不存在")
    return item


def visible(db, actor, workspace_id, request):
    space = db.get(Workspace, workspace_id)
    return actor.is_admin or (space and space.owner_id == actor.id) or request.created_by == actor.id


def request_view(db, item):
    # 返回摘要便于前端在确认时回传并校验；完整消息仍不外发。
    data = serialize(item, exclude={"messages"})
    adoption = db.scalar(select(AssistantAdoption).where(AssistantAdoption.request_id == item.id))
    data["adoption"] = serialize(adoption, exclude={"payload_digest"}) if adoption else None
    data["expired"] = item.status in {"preview", "queued"} and aware(item.expires_at) <= utcnow()
    return data


def prepare(db, settings, actor, workspace_id, payload: AssistantPrepare):
    """读取有权访问的源对象，生成固定预览；此阶段不调用供应商。"""
    policy = policy_view(db, workspace_id)
    source, context, images = collect_source(db, settings, actor, workspace_id, payload, policy)
    _, connection = usable_connection(db, workspace_id, payload.connection_id, source["scopes"], vision=bool(images))
    messages, preview = build_messages(payload.purpose, context, images, policy)
    digest = hashlib.sha256(json.dumps({"workspace_id": workspace_id, "created_by": actor.id,
        "purpose": payload.purpose, "connection_id": connection.id, "connection_revision": connection.revision,
        "policy_revision": policy["revision"], "source": source, "messages": messages},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    item = AssistantRequest(id=new_id("asr"), workspace_id=workspace_id, created_by=actor.id,
        purpose=payload.purpose, connection_id=connection.id, connection_revision=connection.revision,
        policy_revision=policy["revision"], source=source, messages=messages,
        preview={**preview, "image_indices": [image["index"] for image in images], "image_count": len(images),
            "connection": {"id": connection.id, "name": connection.name, "model": connection.model},
            "max_tokens": policy["max_tokens"]},
        input_digest=digest, max_tokens=policy["max_tokens"],
        expires_at=utcnow() + timedelta(minutes=10), status="preview", result={}, usage={}, error={})
    db.add(item)
    audit(db, actor, "assistants.preview", item.id, workspace_id)
    commit(db)
    return request_view(db, item)


def current_day_count(db, workspace_id, actor_id):
    day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(select(func.count()).select_from(AssistantRequest).where(
        AssistantRequest.workspace_id == workspace_id,
        AssistantRequest.created_by == actor_id,
        AssistantRequest.confirmed_at.is_not(None), AssistantRequest.confirmed_at >= day)) or 0


def revalidate(db, actor, request, settings=None):
    permission(db, actor, request.workspace_id, request.purpose)
    policy, connection = usable_connection(db, request.workspace_id, request.connection_id,
        request.source["scopes"], vision=request.preview.get("image_count", 0) > 0)
    if policy["revision"] != request.policy_revision or connection.revision != request.connection_revision:
        raise Problem(409, "PREVIEW_STALE", "空间授权或模型连接已变化，请重新生成预览")
    if request.purpose == "annotation":
        batch = find_batch(db, request.workspace_id, request.source["batch_id"])
        if batch.status != "open" or batch.version_id != request.source["version_id"]:
            raise Problem(409, "PREVIEW_STALE", "标注来源已变化，请重新生成预览")
        from .annotations import reviewer
        if batch.assigned_to and batch.assigned_to != actor.id and not reviewer(db, actor, batch):
            raise Problem(403, "FORBIDDEN", "批次已分配给其他成员")
        for index in request.source["sample_indices"]:
            result = db.scalar(select(AnnotationResult).where(AnnotationResult.batch_id == batch.id,
                AnnotationResult.sample_index == index))
            if (result.revision if result else 0) != request.source["result_revisions"][str(index)] or (result and result.state == "approved"):
                raise Problem(409, "STALE_SAMPLE", "样本已变化，请重新生成预览")
        if settings:
            dataset, version = source(db, request.workspace_id, batch.version_id)
            read_source(settings, dataset, version)
    else:
        inputs(db, request.workspace_id, JobInput(**request.source["job"]))
    return policy, connection


def confirm(db, actor, request, input_digest, *, settings=None):
    if request.created_by != actor.id:
        raise Problem(403, "FORBIDDEN", "只能确认自己创建的请求")
    if input_digest != request.input_digest:
        raise Problem(409, "PREVIEW_STALE", "确认摘要与预览不一致")
    if request.status != "preview":
        if request.status == "queued":
            return request_view(db, request)
        raise Problem(409, "INVALID_STATE", "当前状态不能确认")
    if aware(request.expires_at) <= utcnow() or input_digest != request.input_digest:
        raise Problem(409, "PREVIEW_STALE", "预览已过期或内容已变化，请重新生成")
    # 计数与状态切换在策略行锁内完成，避免并发请求突破每日上限。
    db.execute(update(WorkspaceAIPolicy).where(WorkspaceAIPolicy.id == request.workspace_id)
        .values(revision=WorkspaceAIPolicy.revision))
    db.expire_all()
    policy, connection = revalidate(db, actor, request, settings)
    if current_day_count(db, request.workspace_id, actor.id) >= policy["daily_requests"]:
        raise Problem(429, "DAILY_LIMIT", "今日智能请求次数已达上限")
    changed = db.execute(update(AssistantRequest).where(AssistantRequest.id == request.id,
        AssistantRequest.status == "preview", AssistantRequest.revision == request.revision)
        .values(status="queued", confirmed_at=utcnow(), revision=request.revision + 1)
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise Problem(409, "STATE_CHANGED", "请求状态已变化，请刷新重试")
    audit(db, actor, "assistants.confirm", request.id, request.workspace_id)
    commit(db)
    db.refresh(request)
    return request_view(db, request)


def cancel(db, actor, request):
    if request.created_by != actor.id and not actor.is_admin:
        raise Problem(403, "FORBIDDEN", "只能取消自己创建的请求")
    if request.status in {"cancelled", "applied", "failed"}:
        return request_view(db, request)
    changed = db.execute(update(AssistantRequest).where(AssistantRequest.id == request.id,
        AssistantRequest.status.in_(["preview", "queued", "running", "succeeded"]))
        .values(status="cancelled", revision=AssistantRequest.revision + 1)
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise Problem(409, "STATE_CHANGED", "请求状态已变化，请刷新重试")
    audit(db, actor, "assistants.cancel", request.id, request.workspace_id)
    commit(db)
    db.refresh(request)
    return request_view(db, request)


def _annotation_target(db, actor, request, payload):
    samples = request.result.get("samples", [])
    known = {sample["index"] for sample in samples}
    if payload.fields:
        raise Problem(422, "VALIDATION_ERROR", "标注采纳不使用参数选择")
    if not payload.indices:
        raise Problem(422, "VALIDATION_ERROR", "请选择要采纳的样本")
    if payload.indices and set(payload.indices) - known:
        raise Problem(422, "VALIDATION_ERROR", "所选候选不在本次结果中")
    chosen = [sample for sample in samples if not payload.indices or sample["index"] in payload.indices]
    if not chosen:
        raise Problem(422, "VALIDATION_ERROR", "请选择要采纳的候选")
    batch = find_batch(db, request.workspace_id, request.source["batch_id"])
    revisions = request.source.get("result_revisions", {})
    apply_candidates(db, actor, batch, chosen, revisions, {
        "assistant_request_id": request.id, "connection_id": request.connection_id})
    return {"batch_id": batch.id, "indices": [sample["index"] for sample in chosen]}


def _job_target(db, actor, request, payload):
    suggestions = request.result.get("suggestions") or []
    known = {item["field"] for item in suggestions}
    if payload.indices:
        raise Problem(422, "VALIDATION_ERROR", "参数采纳不使用样本序号")
    if not payload.fields:
        raise Problem(422, "VALIDATION_ERROR", "请选择要采纳的参数")
    if payload.fields and set(payload.fields) - known:
        raise Problem(422, "VALIDATION_ERROR", "所选参数不在本次建议中")
    chosen = [item for item in suggestions if not payload.fields or item["field"] in payload.fields]
    if not chosen:
        raise Problem(422, "VALIDATION_ERROR", "本次结果没有可采纳的参数")
    original = JobInput(**request.source["job"])
    config = {**original.config.model_dump(), **{item["field"]: item["value"] for item in chosen}}
    name = payload.name or f"{original.name[:80]}（智能参数）"
    draft = original.model_copy(update={"name": name, "config": TrainConfig(**config)})
    workspace_access(db, actor, request.workspace_id, "training.write")
    inputs(db, request.workspace_id, draft)
    job = Job(id=new_id("job"), workspace_id=request.workspace_id, created_by=actor.id,
              **draft.model_dump(mode="json"))
    db.add(job)
    audit(db, actor, "jobs.create", job.id, request.workspace_id)
    return {"job_id": job.id, "fields": [item["field"] for item in chosen]}


def apply(db, actor, request, payload):
    if request.created_by != actor.id:
        raise Problem(403, "FORBIDDEN", "只能采纳自己确认的请求")
    permission(db, actor, request.workspace_id, request.purpose, write=True)
    # 同一请求的采纳与取消串行化；SQLite与PostgreSQL都通过写锁保护。
    db.execute(update(AssistantRequest).where(AssistantRequest.id == request.id)
        .values(revision=AssistantRequest.revision).execution_options(synchronize_session=False))
    db.refresh(request)
    digest = hashlib.sha256(json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(select(AssistantAdoption).where(AssistantAdoption.request_id == request.id))
    if existing is not None:
        if existing.payload_digest != digest:
            raise Problem(409, "ALREADY_APPLIED", "此请求已按其他内容采纳，请查看已有结果")
        return serialize(existing)
    if request.status != "succeeded":
        raise Problem(409, "INVALID_STATE", "只有已完成的请求可以采纳")
    target = (_annotation_target if request.purpose == "annotation" else _job_target)(db, actor, request, payload)
    adoption = AssistantAdoption(id=new_id("adp"), request_id=request.id, actor_id=actor.id,
                                 payload_digest=digest, target=target)
    db.add(adoption)
    db.execute(update(AssistantRequest).where(AssistantRequest.id == request.id,
        AssistantRequest.status == "succeeded").values(status="applied", revision=AssistantRequest.revision + 1)
        .execution_options(synchronize_session=False))
    audit(db, actor, "assistants.apply", request.id, request.workspace_id)
    commit(db)
    return serialize(adoption)
