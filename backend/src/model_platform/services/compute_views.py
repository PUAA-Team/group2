from datetime import timedelta

from sqlalchemy import and_, case, func, or_, select

from ..compute_models import ComputeDevice, ComputeNode
from ..database import utcnow
from ..governance_models import DevicePolicy
from .common import serialize
from .resource_policies import node_is_online, policy_allows


def node_view(db, node, settings, *, actor=None):
    value = serialize(node, exclude=("credential_digest", "machine_id", "heartbeat_digest"))
    online = node_is_online(node, settings)
    status = "已撤销" if node.revoked else "待审核" if not node.approved else "离线" if not online else "暂停接收" if not node.enabled else "在线"
    devices = db.execute(select(ComputeDevice, DevicePolicy.value)
        .outerjoin(DevicePolicy, DevicePolicy.id == ComputeDevice.id)
        .where(ComputeDevice.node_id == node.id).order_by(ComputeDevice.kind, ComputeDevice.id))
    value.update(status=status, online=online,
                 devices=[device_view(device, node, online, rule or {}, actor) for device, rule in devices])
    return value


def device_view(device, node, online, rule, actor):
    value = serialize(device)
    status = "失联占用" if device.reserved_execution_id and not online else "使用中" if device.reserved_execution_id else "不可用" if not online or not node.approved or node.revoked or not device.present else "暂停接收" if not node.enabled else "空闲"
    value["status"] = status
    value["purpose"] = rule.get("purpose", "shared")
    if actor is not None:
        value["selectable"] = bool(node.approved and not node.revoked and device.present and policy_allows(rule, actor))
    return value


def resource_summary(db, settings, workspace_id=None):
    cutoff = utcnow() - timedelta(seconds=settings.node_timeout_seconds)
    fresh = ComputeNode.last_seen_at >= cutoff
    approved = and_(ComputeNode.approved.is_(True), ComputeNode.revoked.is_(False))
    online = and_(fresh, approved, ComputeNode.enabled.is_(True))
    scope = [] if workspace_id is None else [ComputeNode.workspace_id == workspace_id]
    total, ready = db.execute(select(func.count(), func.count(case((online, 1))))
                              .select_from(ComputeNode).where(*scope)).one()
    occupied = ComputeDevice.reserved_execution_id.is_not(None)
    disconnected = or_(ComputeNode.last_seen_at.is_(None), ComputeNode.last_seen_at < cutoff)
    grouped = db.execute(select(ComputeDevice.kind, func.count(), func.count(case((occupied, 1))),
                               func.count(case((and_(occupied, disconnected), 1))))
        .join(ComputeNode, ComputeNode.id == ComputeDevice.node_id)
        .where(*scope, approved, or_(ComputeDevice.present.is_(True), occupied)).group_by(ComputeDevice.kind))
    counts = {kind: dict(total=count, occupied=used, disconnected_occupied=lost)
              for kind, count, used, lost in grouped}
    empty = dict(total=0, occupied=0, disconnected_occupied=0)
    return {"nodes": {"total": total, "online": ready}, "cpu": counts.get("cpu", empty), "cuda": counts.get("cuda", empty)}
