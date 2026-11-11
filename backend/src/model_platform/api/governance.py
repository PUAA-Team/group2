from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from ..compute_models import ComputeDevice
from ..errors import Problem, response
from ..governance_schemas import ArchiveInput, BudgetInput, DevicePolicyInput, ReconcileInput
from ..models import Dataset, ModelAsset, User, UserGroup
from ..permissions import require_admin, workspace_access
from ..services.asset_lifecycle import set_archive
from ..services.budgets import budget_view, save_budget, storage_usage
from ..services.common import find_asset
from ..services.compute import get_visible_node
from ..services.execution_reviews import reconcile, review_view
from ..services.monitoring import history
from ..services.resource_policies import device_policy, save_device_policy
from .deps import Actor, Db

router = APIRouter(prefix='/api/v1', tags=['资源治理与归档'])


@router.get('/resources/nodes/{node_id}/history')
def node_history(node_id: str, device_id: str, request: Request, actor: Actor, db: Db,
                 hours: Annotated[int, Query(ge=1, le=168)] = 24):
    node = get_visible_node(db, actor, node_id, 'resources.read')
    return response(request, history(db, node, device_id, hours))


def find_device(db, identifier):
    device = db.get(ComputeDevice, identifier)
    if not device:
        raise Problem(404, 'NOT_FOUND', '设备不存在')
    return device


@router.get('/resources/devices/{device_id}/policy')
def get_policy(device_id: str, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, 'resources.manage')
    find_device(db, device_id)
    return response(request, device_policy(db, device_id))


@router.post('/resources/devices/{device_id}/policy')
def update_policy(device_id: str, payload: DevicePolicyInput, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, 'resources.manage')
    device = find_device(db, device_id)
    node = get_visible_node(db, actor, device.node_id, 'resources.manage')
    return response(request, save_device_policy(db, actor, node, device, payload))


@router.get('/admin/resource-principals')
def principals(request: Request, actor: Actor, db: Db):
    require_admin(db, actor, 'resources.manage')
    return response(request, {'users': [{'id': row.id, 'name': row.display_name} for row in db.scalars(select(User).order_by(User.id))],
        'groups': [{'id': row.id, 'name': row.name} for row in db.scalars(select(UserGroup).order_by(UserGroup.id))]})


@router.get('/admin/groups/{group_id}/budget')
def get_budget(group_id: str, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, 'groups.manage')
    return response(request, budget_view(db, group_id))


@router.post('/admin/groups/{group_id}/budget')
def update_budget(group_id: str, payload: BudgetInput, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, 'groups.manage')
    return response(request, save_budget(db, actor, group_id, payload))


@router.get('/workspaces/{workspace_id}/storage-usage')
def get_storage(workspace_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, 'datasets.read')
    return response(request, storage_usage(db, actor, workspace_id))


@router.post('/workspaces/{workspace_id}/datasets/{asset_id}/archive')
def archive_dataset(workspace_id: str, asset_id: str, payload: ArchiveInput, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, 'datasets.write')
    asset = find_asset(db, Dataset, workspace_id, asset_id)
    return response(request, set_archive(db, actor, asset, payload, 'datasets'))


@router.post('/workspaces/{workspace_id}/models/{asset_id}/archive')
def archive_model(workspace_id: str, asset_id: str, payload: ArchiveInput, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, 'models.write')
    asset = find_asset(db, ModelAsset, workspace_id, asset_id)
    return response(request, set_archive(db, actor, asset, payload, 'models'))


@router.get('/admin/executions/{execution_id}/review')
def execution_review(execution_id: str, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, 'resources.manage')
    return response(request, review_view(db, execution_id, request.app.state.settings))


@router.post('/admin/executions/{execution_id}/reconcile')
def execution_reconcile(execution_id: str, payload: ReconcileInput, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, 'resources.manage')
    return response(request, reconcile(db, actor, execution_id, payload, request.app.state.settings))
