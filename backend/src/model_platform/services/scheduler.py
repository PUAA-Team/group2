from datetime import timedelta

from sqlalchemy import func, select, update

from ..compute_models import ComputeDevice
from ..administration_models import PlatformSetting
from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..job_models import Execution, Job
from ..models import User
from ..permissions import effective_policy, workspace_access
from .common import commit
from .compute import lock_node
from .jobs import ACTIVE, action_for


def assignment(db, execution):
    job = db.get(Job, execution.job_id)
    device = db.get(ComputeDevice, execution.device_id)
    return {"execution_id": execution.id, "job_id": job.id, "kind": job.kind,
            "snapshot": job.snapshot, "device": {"kind": device.kind, "hardware_id": device.hardware_id},
            "event_seq": execution.event_seq}


def claim(db, node, settings, known):
    lock_node(db, node)
    outstanding = db.scalars(select(Execution).where(Execution.node_id == node.id, Execution.finished_at.is_(None))).all()
    for execution in outstanding:
        if execution.id not in known:
            return {**assignment(db, execution), "redelivered": True}
    if not node.approved or not node.enabled or not node.last_seen_at or (utcnow() - aware(node.last_seen_at)).total_seconds() > settings.node_timeout_seconds or len(outstanding) >= node.slots:
        return None
    # 全局策略行串行保护跨节点的总并发上限。
    db.execute(update(PlatformSetting).where(PlatformSetting.id == "platform").values(revision=PlatformSetting.revision))
    from .platform_settings import platform_config
    if db.scalar(select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE))) >= platform_config(db).global_concurrent_jobs:
        db.commit()
        return None
    trainers = node.inventory.get("runtime", {}).get("trainers", [])
    devices = db.scalars(select(ComputeDevice).where(ComputeDevice.node_id == node.id, ComputeDevice.present.is_(True), ComputeDevice.reserved_execution_id.is_(None)).order_by(ComputeDevice.id)).all()
    candidates = db.scalars(select(Job).where(Job.workspace_id == node.workspace_id, Job.status == "queued").order_by(Job.priority.desc(), Job.created_at, Job.id).limit(200)).all()
    for job in candidates:
        if job.snapshot.get("trainer_id") not in trainers or job.node_id and job.node_id != node.id:
            continue
        if job.snapshot.get("config", {}).get("inference") is not None and node.inventory.get("runtime", {}).get("inference_contract_version", 0) < 1:
            continue
        device = next((item for item in devices if item.kind == job.device_kind and item.memory_mb >= job.min_memory_mb
                       and (item.kind != "cuda" or node.inventory.get("runtime", {}).get("cuda_available"))), None)
        if device is None:
            continue
        # 同一用户跨节点领取串行核验，避免两个节点同时突破并发额度。
        db.execute(update(User).where(User.id == job.created_by).values(revision=User.revision).execution_options(synchronize_session=False))
        actor = db.get(User, job.created_by); db.refresh(actor)
        try:
            if not actor.active:
                continue
            workspace_access(db, actor, job.workspace_id, action_for(job.kind, True))
        except Problem:
            continue
        _, quota = effective_policy(db, actor)
        active = select(Job).where(Job.created_by == actor.id, Job.status.in_(ACTIVE))
        count = db.scalar(select(func.count()).select_from(active.subquery()))
        gpu = db.scalar(select(func.count()).select_from(active.where(Job.device_kind == "cuda").subquery()))
        if count >= quota["concurrent_jobs"] or device.kind == "cuda" and gpu >= quota["gpu_count"]:
            continue
        result = db.execute(update(Job).where(Job.id == job.id, Job.status == "queued").values(status="preparing", revision=Job.revision + 1).execution_options(synchronize_session=False))
        if not result.rowcount:
            continue
        execution = Execution(id=new_id("exe"), job_id=job.id, node_id=node.id, device_id=device.id, lease_until=utcnow() + timedelta(seconds=30))
        result = db.execute(update(ComputeDevice).where(ComputeDevice.id == device.id, ComputeDevice.reserved_execution_id.is_(None)).values(reserved_execution_id=execution.id))
        if not result.rowcount:
            db.rollback(); return None
        db.add(execution); commit(db); db.refresh(job)
        return assignment(db, execution)
    db.commit()
    return None
