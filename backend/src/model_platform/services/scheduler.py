from datetime import timedelta

from sqlalchemy import and_, func, or_, select, update

from ..compute_models import ComputeDevice
from ..administration_models import PlatformSetting
from ..database import new_id, utcnow
from ..errors import Problem
from ..governance_models import DevicePolicy
from ..job_models import Execution, Job, Project
from ..models import User
from ..permissions import workspace_access
from .common import commit
from .compute import lock_node
from .jobs import ACTIVE, action_for, personal_capacity_available
from .budgets import allocation_allowed
from .resource_policies import device_allowed, device_fits, node_accepts_tasks, purpose_matches, runtime_fits
from .asset_lifecycle import ensure_active, lock_active

CLAIM_BATCH = 64
QUEUE_KINDS = ("train", "evaluate", "service")


def candidates_for_node(db, node, runtime, devices):
    trainers = runtime.get("trainers", ())
    if not trainers:
        return
    capacities = {}
    for device, rule in devices:
        for kind in QUEUE_KINDS:
            if purpose_matches(rule.get("purpose", "shared"), kind):
                key = kind, device.kind
                capacities[key] = max(capacities.get(key, 0), device.memory_mb)
    if not capacities:
        return
    possible = [and_(Job.kind == kind, Job.device_kind == device_kind, Job.min_memory_mb <= memory)
                for (kind, device_kind), memory in capacities.items()]
    query = (select(Job).where(Job.workspace_id == node.workspace_id, Job.status == "queued",
             or_(Job.node_id.is_(None), Job.node_id == node.id),
             Job.snapshot["trainer_id"].as_string().in_(trainers), or_(*possible))
             .order_by(Job.priority.desc(), Job.created_at, Job.id).limit(CLAIM_BATCH))
    page = query
    while True:
        batch = db.scalars(page).all()
        yield from batch
        if len(batch) < CLAIM_BATCH:
            return
        last = batch[-1]
        page = query.where(or_(Job.priority < last.priority,
            and_(Job.priority == last.priority, Job.created_at > last.created_at),
            and_(Job.priority == last.priority, Job.created_at == last.created_at, Job.id > last.id)))


def assignment(db, execution):
    job = db.get(Job, execution.job_id)
    device = db.get(ComputeDevice, execution.device_id)
    return {"execution_id": execution.id, "job_id": job.id, "kind": job.kind,
            "snapshot": job.snapshot, "device": {"kind": device.kind, "hardware_id": device.hardware_id},
            "event_seq": execution.event_seq}


def claim(db, node, settings, known):
    lock_node(db, node)
    if not node.approved or node.revoked or not node.enabled:
        return None
    outstanding = db.scalars(select(Execution).where(Execution.node_id == node.id, Execution.finished_at.is_(None))).all()
    for execution in outstanding:
        if execution.id not in known:
            return {**assignment(db, execution), "redelivered": True}
    if not node_accepts_tasks(node, settings) or len(outstanding) >= node.slots:
        return None
    if node.inventory.get('runtime', {}).get('execution_contract_version', 0) < 1:
        return None
    # 全局策略行串行保护跨节点的总并发上限。
    db.execute(update(PlatformSetting).where(PlatformSetting.id == "platform").values(revision=PlatformSetting.revision))
    from .platform_settings import platform_config
    if db.scalar(select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE))) >= platform_config(db).global_concurrent_jobs:
        db.commit()
        return None
    runtime = node.inventory.get("runtime", {})
    rows = db.execute(select(ComputeDevice, DevicePolicy.value)
        .outerjoin(DevicePolicy, DevicePolicy.id == ComputeDevice.id)
        .where(ComputeDevice.node_id == node.id, ComputeDevice.present.is_(True),
               ComputeDevice.reserved_execution_id.is_(None)).order_by(ComputeDevice.id))
    devices = [(item, rule or {}) for item, rule in rows if (rule or {}).get("enabled", True)
               and (item.kind != "cuda" or runtime.get("cuda_available"))]
    for job in candidates_for_node(db, node, runtime, devices):
        if not runtime_fits(job, runtime):
            continue
        # 同一用户跨节点领取串行核验，避免两个节点同时突破并发额度。
        db.execute(update(User).where(User.id == job.created_by).values(revision=User.revision).execution_options(synchronize_session=False))
        actor = db.get(User, job.created_by); db.refresh(actor)
        try:
            if not actor.active:
                continue
            # 先锁定并刷新组，再核验继承权限/额度，避免沿用调整前的配置。
            if not allocation_allowed(db, actor, job.device_kind):
                continue
            workspace_access(db, actor, job.workspace_id, action_for(job.kind, True))
            if job.project_id:
                project = db.get(Project, job.project_id)
                if not project or project.workspace_id != job.workspace_id:
                    continue
                lock_active(db, project)
            from ..models import Dataset, DatasetVersion, ModelAsset, ModelVersion
            model_version = db.get(ModelVersion, job.model_version_id)
            ensure_active(db.get(ModelAsset, model_version.model_id))
            if job.dataset_version_id:
                data_version = db.get(DatasetVersion, job.dataset_version_id)
                ensure_active(db.get(Dataset, data_version.dataset_id))
        except Problem:
            continue
        device = next((item for item, rule in devices if device_fits(job, item, runtime)
                       and device_allowed(rule, actor, job.kind)), None)
        if device is None or not personal_capacity_available(db, actor, job.device_kind):
            continue
        result = db.execute(update(Job).where(Job.id == job.id, Job.status == "queued").values(status="preparing", revision=Job.revision + 1).execution_options(synchronize_session=False))
        if not result.rowcount:
            continue
        execution = Execution(id=new_id("exe"), job_id=job.id, node_id=node.id, device_id=device.id, group_id=actor.group_id, lease_until=utcnow() + timedelta(seconds=30))
        result = db.execute(update(ComputeDevice).where(ComputeDevice.id == device.id, ComputeDevice.reserved_execution_id.is_(None)).values(reserved_execution_id=execution.id))
        if not result.rowcount:
            db.rollback(); return None
        db.add(execution); commit(db); db.refresh(job)
        return assignment(db, execution)
    db.commit()
    return None
