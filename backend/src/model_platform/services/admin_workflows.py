from sqlalchemy import func, select

from ..assistant_models import AssistantRequest
from ..data_models import DataOperation
from ..database import aware
from ..models import User, Workspace
from .common import search_query
from .catalog_filters import filter_catalog

PURPOSES = {'annotation': '智能标注', 'parameters': '智能参数', 'logs': '智能日志'}
KINDS = {'clean': '数据清洗', 'split': '数据划分', 'augment': '数据增强'}


def workflow_catalog(db, kind, space, status, q, page, size, filters=None):
    model = DataOperation if kind == 'operations' else AssistantRequest
    # 按列读取，管理列表不加载或返回消息、预览、样本及结果正文。
    columns = [model.id, model.workspace_id, model.created_by, model.created_at, model.status]
    columns += [model.name, model.kind] if kind == 'operations' else [model.purpose, model.usage, model.error]
    query = select(*columns)
    query = filter_catalog(query, model, kind, filters)
    if space:
        query = query.where(model.workspace_id == space)
    if status:
        query = query.where(model.status == status)
    if kind == 'assistants' and q:
        q = next((key for key, name in PURPOSES.items() if q in name), q)
    query = search_query(query, q, model.name if kind == 'operations' else model.purpose)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(model.created_at.desc(), model.id).offset((page - 1) * size).limit(size)).mappings().all()
    users = {row.id: row.display_name for row in db.scalars(select(User).where(User.id.in_({item['created_by'] for item in rows})))}
    spaces = {row.id: row.name for row in db.scalars(select(Workspace).where(Workspace.id.in_({item['workspace_id'] for item in rows})))}
    items = []
    for row in rows:
        tokens = row['usage'].get('total_tokens') if kind == 'assistants' else None
        items.append({'id': row['id'], 'workspace_id': row['workspace_id'], 'workspace_name': spaces.get(row['workspace_id'], '—'),
            'actor_name': users.get(row['created_by'], '—'), 'created_at': aware(row['created_at']).isoformat(),
            'status': row['status'], 'name': row['name'] if kind == 'operations' else PURPOSES.get(row['purpose'], '智能请求'),
            'type_name': KINDS.get(row['kind'], row['kind']) if kind == 'operations' else PURPOSES.get(row['purpose'], row['purpose']),
            'reported_tokens': tokens if type(tokens) is int and tokens >= 0 else None,
            'error_code': row['error'].get('code') if kind == 'assistants' else None})
    return items, {'total': total, 'page': page, 'page_size': size}
