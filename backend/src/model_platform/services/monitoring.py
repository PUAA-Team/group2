from datetime import timedelta
import math

from sqlalchemy import delete, select

from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..governance_models import NodeSample


def save_sample(db, node, devices):
    latest = db.scalar(select(NodeSample.created_at).where(NodeSample.node_id == node.id)
                       .order_by(NodeSample.created_at.desc()).limit(1))
    now = utcnow()
    if latest and (now - aware(latest)).total_seconds() < 30:
        return
    db.add(NodeSample(id=new_id('nsm'), node_id=node.id, seq=node.heartbeat_seq,
        metrics={device.id: {**device.metrics, 'memory_mb': device.memory_mb}
                 for device in devices if device.present}))
    db.execute(delete(NodeSample).where(NodeSample.created_at < now - timedelta(days=7)))


def history(db, node, device_id, hours):
    from ..compute_models import ComputeDevice
    device = db.get(ComputeDevice, device_id)
    if not device or device.node_id != node.id:
        raise Problem(404, 'NOT_FOUND', '设备不存在')
    # 只取所选设备的JSON，避免把整节点的所有设备历史载入内存。
    rows = db.execute(select(NodeSample.created_at, NodeSample.metrics[device_id])
        .where(NodeSample.node_id == node.id, NodeSample.created_at >= utcnow() - timedelta(hours=hours))
        .order_by(NodeSample.created_at)).all()
    stride = max(1, math.ceil(len(rows) / 240))
    selected = rows[::stride]
    if rows and selected[-1] != rows[-1]:
        selected = selected[:239] + [rows[-1]]
    return {'node_id': node.id, 'device_id': device.id, 'hours': hours,
        'sampling_seconds': 30, 'stride': stride,
        'points': [{'at': aware(at).isoformat(), 'utilization': (metrics or {}).get('utilization'),
                    'used_memory_mb': (metrics or {}).get('used_memory_mb'),
                    'memory_mb': (metrics or {}).get('memory_mb')} for at, metrics in selected]}
