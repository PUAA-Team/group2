from collections import Counter

from sqlalchemy import func, or_, select, and_

from ..assistant_models import AssistantRequest
from ..data_models import DataOperation
from ..database import aware
from ..governance_models import StoredObject
from ..job_models import Execution, Job
from ..models import DatasetVersion, ModelVersion


def asset_bytes(db, kind, identifier):
    if kind == 'datasets':
        versions = select(DatasetVersion.id).where(DatasetVersion.dataset_id == identifier)
        operations = select(DataOperation.id).where(DataOperation.version_id.in_(versions))
        condition = or_(and_(StoredObject.kind == 'dataset', StoredObject.object_id.in_(versions)),
                        and_(StoredObject.kind == 'candidate', StoredObject.object_id.in_(operations)))
    else:
        versions = select(ModelVersion.id).where(ModelVersion.model_id == identifier)
        jobs = select(Job.id).where(Job.model_version_id.in_(versions))
        condition = and_(StoredObject.kind == 'artifact', StoredObject.object_id.in_(jobs))
    return db.scalar(select(func.sum(StoredObject.size_bytes)).where(condition)) or 0


def resource_totals(db, actions, space, kinds):
    allowed = (['dataset', 'candidate'] if 'datasets.read' in actions else []) + (['artifact'] if 'models.read' in actions else [])
    files = select(func.sum(StoredObject.size_bytes)).where(StoredObject.kind.in_(allowed))
    if space:
        files = files.where(StoredObject.workspace_id == space)
    executions = select(Execution).join(Job).where(Job.device_kind == 'cuda', Job.kind.in_(kinds), Execution.finished_at.is_not(None))
    if space:
        executions = executions.where(Job.workspace_id == space)
    seconds = 0
    for row in db.scalars(executions):
        duration = (aware(row.finished_at) - aware(row.created_at)).total_seconds()
        if duration >= 0:
            seconds += duration
    query = select(AssistantRequest).where(AssistantRequest.confirmed_at.is_not(None))
    if space:
        query = query.where(AssistantRequest.workspace_id == space)
    requests = db.scalars(query).all() if 'assistants.use' in actions else []
    known_tokens = [item.usage['total_tokens'] for item in requests if type(item.usage.get('total_tokens')) is int]
    return {'storage_bytes': (db.scalar(files) or 0) if allowed else None, 'gpu_reserved_seconds': round(seconds) if kinds else None,
        'confirmed_assistant_requests': len(requests) if 'assistants.use' in actions else None,
        'reported_assistant_tokens': sum(known_tokens) if known_tokens else None,
        'assistant_states': dict(Counter(item.status for item in requests))}
