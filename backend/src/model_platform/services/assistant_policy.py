from sqlalchemy import select

from ..administration_models import ModelConnection
from ..assistant_models import WorkspaceAIPolicy
from ..assistant_schemas import AIPolicyInput
from ..errors import Problem
from .common import audit, commit, revision_update


def policy_view(db, workspace_id):
    record = db.get(WorkspaceAIPolicy, workspace_id)
    return {**AIPolicyInput(revision=0).model_dump(), **(record.value if record else {}),
            "revision": record.revision if record else 0}


def public_connections(db, identifiers=None):
    query = select(ModelConnection).where(ModelConnection.active.is_(True), ModelConnection.secret_ref.is_not(None))
    if identifiers is not None:
        query = query.where(ModelConnection.id.in_(identifiers))
    return [{"id": item.id, "name": item.name, "model": item.model, "endpoint": item.endpoint,
             "capabilities": item.capabilities} for item in db.scalars(query.order_by(ModelConnection.created_at))]


def save_policy(db, actor, workspace_id, payload):
    for identifier in payload.connection_ids:
        if db.get(ModelConnection, identifier) is None:
            raise Problem(422, "INVALID_CONNECTION", "所选连接不存在")
    record = db.get(WorkspaceAIPolicy, workspace_id)
    values = payload.model_dump(exclude={"revision"})
    if record:
        revision_update(db, record, {"value": values}, payload.revision)
    else:
        if payload.revision != 0:
            raise Problem(412, "REVISION_MISMATCH", "空间策略已更新，请重新读取")
        db.add(WorkspaceAIPolicy(id=workspace_id, value=values))
    audit(db, actor, "assistants.policy.update", workspace_id, workspace_id)
    commit(db)
    return policy_view(db, workspace_id)


def usable_connection(db, workspace_id, connection_id, scopes, *, vision=False):
    policy = policy_view(db, workspace_id)
    if not policy["enabled"] or connection_id not in policy["connection_ids"] or set(scopes) - set(policy["scopes"]):
        raise Problem(403, "OUTBOUND_NOT_AUTHORIZED", "当前空间尚未授权此连接及所需的外发类别")
    item = db.get(ModelConnection, connection_id)
    if item is None or not item.active or not item.secret_ref:
        raise Problem(409, "CONNECTION_DISABLED", "模型连接未启用或未配置凭据")
    if ("vision" if vision else "text") not in item.capabilities:
        raise Problem(422, "MODEL_CAPABILITY_REQUIRED", "所选连接不支持本次所需的文本或视觉能力")
    return policy, item
