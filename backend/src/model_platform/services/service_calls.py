from datetime import timedelta
import secrets

from sqlalchemy import func, select

from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..job_models import Job, ServiceCall, ServiceKey
from ..models import User
from ..permissions import workspace_access
from ..security import digest
from .common import audit, commit, serialize
from .executions import owned_execution


def create_call(db, actor, job, payload):
    workspace_access(db, actor, job.workspace_id, "services.invoke")
    if job.kind != "service" or job.status != "ready":
        raise Problem(409, "SERVICE_NOT_READY", "服务尚未就绪")
    wants_image = job.snapshot.get("task_type") == "image_classification"
    if bool(payload.image_base64) != wants_image:
        raise Problem(422, "INPUT_MISMATCH", "输入与服务任务类型不匹配")
    pending = db.scalar(select(func.count()).select_from(ServiceCall).where(ServiceCall.job_id == job.id, ServiceCall.status == "pending"))
    if pending >= 32:
        raise Problem(429, "QUEUE_FULL", "服务请求队列已满")
    call = ServiceCall(id=new_id("cal"), job_id=job.id, created_by=actor.id, input=payload.model_dump(exclude_none=True))
    db.add(call); audit(db, actor, "services.invoke", call.id, job.workspace_id); commit(db)
    return serialize(call)


def complete_call(db, node, execution_id, call_id, payload):
    execution, job = owned_execution(db, node, execution_id, lock=True)
    call = db.get(ServiceCall, call_id)
    if not call or call.job_id != job.id:
        raise Problem(404, "NOT_FOUND", "调用不存在")
    status, result = payload.status, payload.result
    profile = job.snapshot.get("config", {}).get("inference") or {}
    if status == "succeeded" and profile.get("mode") == "label" and (result.get("label") not in profile["labels"] or result.get("text") != result.get("label")):
        status, result = "failed", {"error": "Worker输出不符合部署标签约束，请检查运行版本"}
    if call.status != "pending":
        if call.status != status or call.result != result:
            raise Problem(409, "CALL_CONFLICT", "调用结果冲突")
    elif execution.finished_at:
        raise Problem(409, "INVALID_STATE", "执行已结束")
    else:
        call.status, call.result = status, result
        commit(db)
    return {"accepted": True}


def create_key(db, actor, workspace_id, payload):
    workspace_access(db, actor, workspace_id, "services.write")
    job = db.get(Job, payload.job_id)
    if not job or job.workspace_id != workspace_id or job.kind != "service":
        raise Problem(422, "INVALID_SERVICE", "请选择本空间服务")
    raw = "mtk_" + secrets.token_urlsafe(36)
    key = ServiceKey(id=new_id("key"), workspace_id=workspace_id, job_id=job.id, created_by=actor.id,
                     name=payload.name, token_digest=digest(raw), expires_at=utcnow() + timedelta(days=payload.days))
    db.add(key); audit(db, actor, "service_keys.create", key.id, workspace_id); commit(db)
    return {**serialize(key), "key": raw}


def key_actor(db, raw, job_id):
    key = db.scalar(select(ServiceKey).where(ServiceKey.token_digest == digest(raw))) if raw else None
    if not key or key.revoked_at or aware(key.expires_at) <= utcnow() or key.job_id != job_id:
        raise Problem(401, "INVALID_API_KEY", "API KEY 无效或未授权此服务")
    actor = db.get(User, key.created_by)
    if not actor or not actor.active:
        raise Problem(401, "INVALID_API_KEY", "API KEY 创建者已停用")
    workspace_access(db, actor, key.workspace_id, "services.invoke")
    return actor, key
