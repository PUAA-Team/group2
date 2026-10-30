from sqlalchemy import select

from ..compute_models import ComputeDevice
from ..database import aware, utcnow
from .common import serialize


def node_view(db, node, settings):
    value = serialize(node, exclude=("credential_digest", "machine_id", "heartbeat_digest"))
    online = bool(node.last_seen_at and (utcnow() - aware(node.last_seen_at)).total_seconds() <= settings.node_timeout_seconds)
    status = "已撤销" if node.revoked else "待审核" if not node.approved else "离线" if not online else "暂停接收" if not node.enabled else "在线"
    devices = db.scalars(select(ComputeDevice).where(ComputeDevice.node_id == node.id).order_by(ComputeDevice.kind, ComputeDevice.id)).all()
    value.update(status=status, online=online, devices=[device_view(device, node, online) for device in devices])
    return value


def device_view(device, node, online):
    value = serialize(device)
    status = "失联占用" if device.reserved_execution_id and not online else "使用中" if device.reserved_execution_id else "不可用" if not online or not node.approved or node.revoked or not device.present else "暂停接收" if not node.enabled else "空闲"
    value["status"] = status
    return value
