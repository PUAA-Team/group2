from sqlalchemy import case, func, select, update

from ..errors import Problem
from ..governance_models import GroupBudget, StoredObject
from ..governance_schemas import BudgetInput
from ..job_models import Execution, Job
from ..models import User, UserGroup
from ..permissions import effective_policy
from .common import audit, commit, revision_update

GIB = 1024 ** 3


def lock_group(db, identifier):
    if identifier:
        db.execute(update(UserGroup).where(UserGroup.id == identifier)
            .values(revision=UserGroup.revision).execution_options(synchronize_session=False))
        group = db.get(UserGroup, identifier)
        if group:
            db.refresh(group)


def budget_view(db, group_id):
    if not db.get(UserGroup, group_id):
        raise Problem(404, "NOT_FOUND", "用户组不存在")
    row = db.get(GroupBudget, group_id)
    count, gpu = db.execute(select(func.count(), func.sum(case((Job.device_kind == "cuda", 1), else_=0)))
        .select_from(Execution).join(Job, Job.id == Execution.job_id)
        .where(Execution.group_id == group_id, Execution.finished_at.is_(None))).one()
    used = db.scalar(select(func.sum(StoredObject.size_bytes)).where(StoredObject.group_id == group_id)) or 0
    return {**BudgetInput(revision=0).model_dump(), **(row.value if row else {}),
        "revision": row.revision if row else 0, "usage": {"concurrent_jobs": count, "gpu_count": gpu or 0, "storage_bytes": used}}


def save_budget(db, actor, group_id, payload):
    if not db.get(UserGroup, group_id):
        raise Problem(404, "NOT_FOUND", "用户组不存在")
    lock_group(db, group_id)
    row = db.get(GroupBudget, group_id)
    values = payload.model_dump(exclude={"revision"})
    if row:
        revision_update(db, row, {"value": values}, payload.revision)
    elif payload.revision != 0:
        raise Problem(412, "REVISION_MISMATCH", "预算已更新，请重新读取")
    else:
        db.add(GroupBudget(id=group_id, value=values))
    audit(db, actor, "groups.budget.update", group_id)
    commit(db)
    return budget_view(db, group_id)


def allocation_allowed(db, actor, kind, *, lock=True):
    if not actor.group_id:
        return True
    if lock:
        lock_group(db, actor.group_id)
    budget = budget_view(db, actor.group_id)
    for key in ("concurrent_jobs", "gpu_count"):
        if key == "gpu_count" and kind != "cuda":
            continue
        if budget[key] is not None and budget["usage"][key] >= budget[key]:
            return False
    return True


def owner_bytes(db, owner_id):
    return db.scalar(select(func.sum(StoredObject.size_bytes)).where(StoredObject.owner_id == owner_id)) or 0


def charge_objects(db, actor, objects):
    """和业务引用共用事务；固定写入时的所有者与计入组。"""
    db.execute(update(User).where(User.id == actor.id).values(revision=User.revision)
        .execution_options(synchronize_session=False))
    db.refresh(actor)
    lock_group(db, actor.group_id)
    pending = []
    for item in objects:
        existing = db.get(StoredObject, item["id"])
        if existing:
            if existing.storage_key != item["storage_key"] or existing.size_bytes != item["size_bytes"]:
                raise Problem(409, "STORAGE_CONFLICT", "存储对象与已有记录不一致")
        else:
            pending.append(item)
    delta = sum(item["size_bytes"] for item in pending)
    _, quota = effective_policy(db, actor)
    if owner_bytes(db, actor.id) + delta > quota["storage_gib"] * GIB:
        raise Problem(413, "STORAGE_LIMIT", "个人存储额度不足，请联系管理员调整额度")
    if actor.group_id:
        budget = budget_view(db, actor.group_id)
        if budget["storage_gib"] is not None and budget["usage"]["storage_bytes"] + delta > budget["storage_gib"] * GIB:
            raise Problem(413, "GROUP_STORAGE_LIMIT", "用户组共享存储额度不足")
    for item in pending:
        db.add(StoredObject(**item, owner_id=actor.id, group_id=actor.group_id))
    db.flush()


def storage_usage(db, actor, workspace_id):
    _, quota = effective_policy(db, actor)
    categories = dict(db.execute(select(StoredObject.kind, func.sum(StoredObject.size_bytes))
        .where(StoredObject.workspace_id == workspace_id).group_by(StoredObject.kind)).all())
    unattributed = db.scalar(select(func.sum(StoredObject.size_bytes)).where(
        StoredObject.workspace_id == workspace_id, StoredObject.owner_id.is_(None))) or 0
    return {"personal_bytes": owner_bytes(db, actor.id), "personal_limit_bytes": quota["storage_gib"] * GIB,
        "workspace_bytes": sum(categories.values()), "categories": categories, "unattributed_bytes": unattributed,
        "group": budget_view(db, actor.group_id) if actor.group_id else None}
