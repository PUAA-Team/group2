import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ..compute_models import ComputeDevice, ComputeNode, Enrollment
from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..models import User, Workspace
from ..permissions import require_action, workspace_access
from ..security import digest
from .common import audit, commit, revision_update
from .compute_views import node_view
from .join_commands import make_commands
from .worker_bundle import build_bundle


def inventory_update(db, node, inventory):
    node.inventory = inventory.model_dump(mode="json")
    node.last_inventory_at = utcnow()
    devices = {device.hardware_id: device for device in db.scalars(select(ComputeDevice).where(ComputeDevice.node_id == node.id))}
    for device in devices.values():
        device.present = False
    for reported in inventory.devices:
        hardware = f"cpu:{node.machine_id}" if reported.kind == "cpu" else f"nvidia:{reported.uuid}"
        device = devices.get(hardware)
        if not device:
            device = ComputeDevice(id=new_id("dev"), node_id=node.id, hardware_id=hardware, kind=reported.kind)
            db.add(device)
        device.name, device.memory_mb, device.present = reported.name, reported.memory_mb, True
        device.metrics = {"utilization": reported.utilization, "used_memory_mb": reported.used_memory_mb, "driver": reported.driver}


def create_enrollment(db, settings, actor, payload, *, local=False):
    workspace_access(db, actor, payload.workspace_id, "resources.manage")
    if payload.auto_approve and not actor.is_admin:
        raise Problem(403, "FORBIDDEN", "自动准入仅供管理员设置")
    secret = secrets.token_urlsafe(32)
    enrollment = Enrollment(id=new_id("enr"), workspace_id=payload.workspace_id, created_by=actor.id,
                            name=payload.name, code_digest=digest(secret), auto_approve=payload.auto_approve,
                            expires_at=utcnow() + timedelta(seconds=settings.enrollment_seconds))
    db.add(enrollment)
    audit(db, actor, "resources.enrollment.create", enrollment.id, payload.workspace_id)
    commit(db)
    _, bundle_sha = build_bundle(settings)
    raw_code = f"{enrollment.id}.{secret}"
    commands = make_commands(payload, raw_code, bundle_sha)
    view = {"id": enrollment.id, "expires_at": aware(enrollment.expires_at).isoformat(), **commands}
    return (view, raw_code) if local else view


def register_node(db, settings, payload):
    parts = payload.join_code.split(".", 1)
    if len(parts) != 2:
        raise Problem(401, "INVALID_ENROLLMENT", "接入码无效或已过期")
    enrollment = db.get(Enrollment, parts[0])
    if not enrollment or not hmac.compare_digest(enrollment.code_digest, digest(parts[1])):
        raise Problem(401, "INVALID_ENROLLMENT", "接入码无效或已过期")
    # 同一申请的并发注册串行完成；SQLite 写锁也保护硬件唯一性检查。
    db.execute(update(Enrollment).where(Enrollment.id == enrollment.id).values(code_digest=Enrollment.code_digest))
    db.refresh(enrollment)
    if enrollment.revoked_at or aware(enrollment.expires_at) <= utcnow():
        raise Problem(401, "INVALID_ENROLLMENT", "接入码无效或已过期")
    actor = db.get(User, enrollment.created_by)
    if not actor or not actor.active:
        raise Problem(403, "FORBIDDEN", "接入授权已撤销")
    workspace_access(db, actor, enrollment.workspace_id, "resources.manage")
    if enrollment.consumed_node_id:
        node = db.get(ComputeNode, enrollment.consumed_node_id)
        if node and not node.revoked and node.installation_id == payload.installation_id and hmac.compare_digest(node.credential_digest, payload.credential_digest):
            return register_receipt(node, settings)
        raise Problem(409, "ENROLLMENT_USED", "接入码已使用")
    existing = db.scalar(select(ComputeNode).where(ComputeNode.machine_id == payload.machine_id))
    if existing:
        if not existing.revoked or existing.active_executions or db.scalar(select(ComputeDevice.id).where(ComputeDevice.node_id == existing.id, ComputeDevice.reserved_execution_id.is_not(None)).limit(1)):
            raise Problem(409, "NODE_EXISTS", "该机器已接入，请使用原工作目录，或先撤销旧节点")
        node = existing
        node.installation_id, node.credential_digest = payload.installation_id, payload.credential_digest
        node.workspace_id, node.name = enrollment.workspace_id, enrollment.name
        node.revoked, node.enabled, node.approved = False, True, enrollment.auto_approve
        node.heartbeat_seq, node.heartbeat_digest = 0, None
        node.revision += 1
    else:
        node = ComputeNode(id=new_id("nod"), workspace_id=enrollment.workspace_id, name=enrollment.name,
                           machine_id=payload.machine_id, installation_id=payload.installation_id,
                           credential_digest=payload.credential_digest, approved=enrollment.auto_approve)
        db.add(node)
    node.slots, node.last_seen_at = payload.slots, utcnow()
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Problem(409, "CONFLICT", "安装标识或凭据已被其他节点使用") from None
    inventory_update(db, node, payload.inventory)
    enrollment.consumed_node_id, enrollment.consumed_at = node.id, utcnow()
    audit(db, actor, "resources.register", node.id, node.workspace_id)
    commit(db)
    return register_receipt(node, settings)


def register_receipt(node, settings):
    return {"node_id": node.id, "approved": node.approved, "enabled": node.enabled,
            "heartbeat_seconds": settings.heartbeat_seconds, "next_seq": node.heartbeat_seq + 1}


def heartbeat(db, node, payload, settings):
    fingerprint = hashlib.sha256(json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    result = db.execute(update(ComputeNode).where(ComputeNode.id == node.id, ComputeNode.heartbeat_seq < payload.seq)
                        .values(heartbeat_seq=payload.seq, heartbeat_digest=fingerprint, last_seen_at=utcnow(),
                                active_executions=payload.active_executions).execution_options(synchronize_session=False))
    db.refresh(node)
    if result.rowcount == 0:
        if payload.seq != node.heartbeat_seq or node.heartbeat_digest != fingerprint:
            raise Problem(409, "STALE_HEARTBEAT", "心跳序号冲突", [{"loc": ["seq"], "type": "conflict", "message": str(node.heartbeat_seq + 1)}])
    by_hardware = {device.hardware_id: device for device in db.scalars(select(ComputeDevice).where(ComputeDevice.node_id == node.id))}
    if result.rowcount:
        for reported in payload.metrics:
            hardware = f"cpu:{node.machine_id}" if reported.kind == "cpu" else f"nvidia:{reported.uuid}"
            if hardware in by_hardware:
                by_hardware[hardware].metrics = {"utilization": reported.utilization, "used_memory_mb": reported.used_memory_mb, "driver": reported.driver}
    commit(db)
    return {**register_receipt(node, settings), "probe_request_id": node.probe_request_id, "controls": []}


def get_visible_node(db, actor, node_id, action):
    node = db.get(ComputeNode, node_id)
    if not node:
        raise Problem(404, "NOT_FOUND", "节点不存在")
    workspace_access(db, actor, node.workspace_id, action)
    return node


def node_busy(db, node):
    return bool(node.active_executions or db.scalar(select(ComputeDevice.id).where(ComputeDevice.node_id == node.id, ComputeDevice.reserved_execution_id.is_not(None)).limit(1)))


def lock_node(db, node):
    if db.bind.dialect.name == "sqlite":
        db.execute(update(ComputeNode).where(ComputeNode.id == node.id).values(revision=ComputeNode.revision)
                   .execution_options(synchronize_session=False))
        db.refresh(node)
    else:
        db.scalars(select(ComputeNode).where(ComputeNode.id == node.id).with_for_update().execution_options(populate_existing=True)).one()


def update_node(db, settings, actor, node, payload, expected):
    lock_node(db, node)
    values = payload.model_dump(exclude_unset=True)
    if "approved" in values and not actor.is_admin:
        raise Problem(403, "FORBIDDEN", "节点审核需要管理员权限")
    if "workspace_id" in values and values["workspace_id"] != node.workspace_id:
        if not actor.is_admin:
            raise Problem(403, "FORBIDDEN", "节点分配需要管理员权限")
        if node_busy(db, node):
            raise Problem(409, "CONFLICT", "节点仍有执行，不能调整分配")
        if not db.get(Workspace, values["workspace_id"]):
            raise Problem(422, "VALIDATION_ERROR", "工作空间不存在")
    revision_update(db, node, values, expected)
    audit(db, actor, "resources.update", node.id, node.workspace_id)
    commit(db)
    return node_view(db, node, settings)
