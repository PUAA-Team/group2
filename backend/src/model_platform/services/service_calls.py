from datetime import timedelta
import secrets

from sqlalchemy import func, select, update

from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..job_models import Job, ServiceCall, ServiceKey
from ..models import User
from ..permissions import workspace_access
from ..security import digest
from .common import audit, commit, serialize
from .executions import owned_execution
from .call_lifecycle import finish_call


def create_call(db, actor, job, payload, service_key=None):
    workspace_access(db, actor, job.workspace_id, "services.invoke")
    if service_key is not None:
        lock_key(db, service_key)
        if service_key.revoked_at or aware(service_key.expires_at) <= utcnow():
            raise Problem(401, 'INVALID_API_KEY', 'API KEY 无效或未授权此服务')
    # 同一服务串行检查状态和队列容量，避免停止竞争及并发突破32条上限。
    locked = db.execute(update(Job).where(Job.id == job.id, Job.kind == 'service', Job.status == 'ready')
        .values(revision=Job.revision).execution_options(synchronize_session=False))
    if locked.rowcount != 1:
        raise Problem(409, "SERVICE_NOT_READY", "服务尚未就绪")
    db.refresh(job)
    wants_image = job.snapshot.get("task_type") == "image_classification"
    if bool(payload.image_base64) != wants_image:
        raise Problem(422, "INPUT_MISMATCH", "输入与服务任务类型不匹配")
    pending = db.scalar(select(func.count()).select_from(ServiceCall).where(ServiceCall.job_id == job.id, ServiceCall.status == "pending"))
    if pending >= 32:
        raise Problem(429, "QUEUE_FULL", "服务请求队列已满")
    call = ServiceCall(id=new_id("cal"), job_id=job.id, created_by=actor.id, input=payload.model_dump(exclude_none=True),
        service_key_id=service_key.id if service_key is not None else None)
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
        finish_call(call, status, result)
        commit(db)
    return {"accepted": True}


def create_key(db, actor, workspace_id, payload, *, expires_at=None, commit_now=True):
    workspace_access(db, actor, workspace_id, "services.write")
    job = db.get(Job, payload.job_id)
    if not job or job.workspace_id != workspace_id or job.kind != "service":
        raise Problem(422, "INVALID_SERVICE", "请选择本空间服务")
    raw = "mtk_" + secrets.token_urlsafe(36)
    key = ServiceKey(id=new_id("key"), workspace_id=workspace_id, job_id=job.id, created_by=actor.id,
                     name=payload.name, token_digest=digest(raw), expires_at=expires_at or utcnow() + timedelta(days=payload.days))
    db.add(key); audit(db, actor, "service_keys.create", key.id, workspace_id)
    db.flush()
    if commit_now:
        commit(db)
    return {**serialize(key), "key": raw}


def rotate_key(db, actor, workspace_id, key_id):
    from ..job_schemas import KeyInput
    workspace_access(db, actor, workspace_id, "services.write")
    key = db.get(ServiceKey, key_id)
    if not key or key.workspace_id != workspace_id or key.created_by != actor.id:
        raise Problem(404, "NOT_FOUND", "密钥不存在")
    lock_key(db, key)
    if key.revoked_at or aware(key.expires_at) <= utcnow():
        raise Problem(409, "KEY_INACTIVE", "已撤销或过期的密钥不能轮换")
    changed = db.execute(update(ServiceKey).where(ServiceKey.id == key.id,
        ServiceKey.revoked_at.is_(None), ServiceKey.expires_at > utcnow())
        .values(revoked_at=utcnow(), revision=ServiceKey.revision + 1).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise Problem(409, "KEY_INACTIVE", "密钥状态已变化，请刷新")
    result = create_key(db, actor, workspace_id, KeyInput(name=key.name, job_id=key.job_id),
                        expires_at=key.expires_at, commit_now=False)
    audit(db, actor, "service_keys.rotate", key.id, workspace_id)
    commit(db)
    return result


def key_actor(db, raw, job_id):
    key = db.scalar(select(ServiceKey).where(ServiceKey.token_digest == digest(raw))) if raw else None
    if not key or key.revoked_at or aware(key.expires_at) <= utcnow() or key.job_id != job_id:
        raise Problem(401, "INVALID_API_KEY", "API KEY 无效或未授权此服务")
    actor = db.get(User, key.created_by)
    if not actor or not actor.active:
        raise Problem(401, "INVALID_API_KEY", "API KEY 创建者已停用")
    workspace_access(db, actor, key.workspace_id, "services.invoke")
    return actor, key


def lock_key(db, key):
    db.execute(update(ServiceKey).where(ServiceKey.id == key.id).values(revision=ServiceKey.revision)
        .execution_options(synchronize_session=False))
    db.refresh(key)


def own_key(db, actor, workspace_id, key_id):
    workspace_access(db, actor, workspace_id, 'services.write')
    key = db.get(ServiceKey, key_id)
    if not key or key.workspace_id != workspace_id or key.created_by != actor.id:
        raise Problem(404, 'NOT_FOUND', '密钥不存在')
    lock_key(db, key)
    return key


def revoke(db, actor, workspace_id, key_id):
    key = own_key(db, actor, workspace_id, key_id)
    if key.revoked_at is None:
        key.revoked_at, key.revision = utcnow(), key.revision + 1
        audit(db, actor, 'service_keys.revoke', key.id, workspace_id); commit(db)
    return serialize(key)


def change_expiry(db, actor, workspace_id, key_id, payload, expected):
    key = own_key(db, actor, workspace_id, key_id)
    if key.revision != expected:
        raise Problem(412, 'REVISION_MISMATCH', '密钥已更新，请刷新重试')
    if key.revoked_at is not None:
        raise Problem(409, 'KEY_INACTIVE', '已撤销的密钥不能恢复')
    now = utcnow()
    if not now < payload.expires_at <= now + timedelta(days=365):
        raise Problem(422, 'INVALID_EXPIRY', '到期时间需要在当前时间之后365天以内')
    key.expires_at, key.revision = payload.expires_at, key.revision + 1
    audit(db, actor, 'service_keys.expiry', key.id, workspace_id); commit(db)
    return serialize(key)


def list_keys(db, actor, workspace_id, job_id=None, status='all'):
    workspace_access(db, actor, workspace_id, 'services.read')
    query = select(ServiceKey).where(ServiceKey.workspace_id == workspace_id, ServiceKey.created_by == actor.id)
    if job_id:
        query = query.where(ServiceKey.job_id == job_id)
    now = utcnow()
    if status == 'active':
        query = query.where(ServiceKey.revoked_at.is_(None), ServiceKey.expires_at > now)
    elif status == 'expired':
        query = query.where(ServiceKey.revoked_at.is_(None), ServiceKey.expires_at <= now)
    elif status == 'revoked':
        query = query.where(ServiceKey.revoked_at.is_not(None))
    keys = db.scalars(query.order_by(ServiceKey.created_at.desc(), ServiceKey.id).limit(100)).all()
    usage = {key: (count, latest) for key, count, latest in db.execute(select(ServiceCall.service_key_id,
        func.count(), func.max(ServiceCall.created_at)).where(ServiceCall.service_key_id.in_([row.id for row in keys]))
        .group_by(ServiceCall.service_key_id))}
    return [{**serialize(key), 'masked_identifier': '••••' + key.id[-8:], 'recorded_calls': usage.get(key.id, (0, None))[0],
        'last_called_at': aware(usage[key.id][1]).isoformat() if key.id in usage else None} for key in keys]
