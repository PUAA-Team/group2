from sqlalchemy import select, update

from ..compute_models import ComputeDevice, ComputeNode
from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..governance_models import ExecutionReview
from ..job_models import Execution, Job, ServiceCall
from .call_lifecycle import finish_call
from .common import audit, commit, serialize
from .compute import lock_node


def review_view(db, identifier, settings):
    execution = db.get(Execution, identifier)
    if not execution:
        raise Problem(404, 'NOT_FOUND', '执行不存在')
    node, job = db.get(ComputeNode, execution.node_id), db.get(Job, execution.job_id)
    review = db.scalar(select(ExecutionReview).where(ExecutionReview.execution_id == identifier))
    online = bool(node.last_seen_at and (utcnow() - aware(node.last_seen_at)).total_seconds() <= settings.node_timeout_seconds)
    return {'execution': serialize(execution), 'job': {'id': job.id, 'name': job.name, 'status': job.status, 'revision': job.revision},
        'node': {'id': node.id, 'name': node.name, 'enabled': node.enabled, 'online': online,
                 'last_seen_at': aware(node.last_seen_at).isoformat() if node.last_seen_at else None,
                 'active_executions': node.active_executions}, 'review': serialize(review) if review else None}


def reconcile(db, actor, identifier, payload, settings):
    execution = db.get(Execution, identifier)
    if not execution:
        raise Problem(404, 'NOT_FOUND', '执行不存在')
    node = db.get(ComputeNode, execution.node_id)
    lock_node(db, node)
    db.execute(update(Execution).where(Execution.id == identifier).values(event_seq=Execution.event_seq)
               .execution_options(synchronize_session=False))
    db.refresh(execution)
    job = db.get(Job, execution.job_id)
    if execution.finished_at:
        raise Problem(409, 'EXECUTION_FINISHED', '执行已经结束，不能重复人工结案')
    if node.enabled:
        raise Problem(409, 'NODE_NOT_PAUSED', '请先暂停节点接收任务')
    online = bool(node.last_seen_at and (utcnow() - aware(node.last_seen_at)).total_seconds() <= settings.node_timeout_seconds)
    if online and identifier in node.active_executions:
        raise Problem(409, 'PROCESS_STILL_REPORTED', '在线节点仍报告该执行，请先在节点上核查并停止进程')
    changed = db.execute(update(Job).where(Job.id == job.id, Job.revision == payload.revision)
        .values(status=payload.outcome, error='人工核查结案：' + payload.reason, revision=Job.revision + 1)
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise Problem(412, 'REVISION_MISMATCH', '任务已更新，请重新核查')
    db.add(ExecutionReview(id=new_id('rev'), execution_id=identifier, actor_id=actor.id,
        reason=payload.reason, outcome=payload.outcome))
    execution.status, execution.finished_at, execution.finish_digest = payload.outcome, utcnow(), 'manual:' + new_id('rev')
    db.execute(update(ComputeDevice).where(ComputeDevice.id == execution.device_id,
        ComputeDevice.reserved_execution_id == identifier).values(reserved_execution_id=None))
    for call in db.scalars(select(ServiceCall).where(ServiceCall.job_id == job.id, ServiceCall.status == 'pending')):
        finish_call(call, 'failed', {'error': '服务执行已人工结案'})
    audit(db, actor, 'resources.execution.reconcile', identifier, job.workspace_id)
    commit(db)
    db.refresh(job)
    return review_view(db, identifier, settings)
