from typing import Literal

from fastapi import APIRouter, Request
from sqlalchemy import select

from ..errors import response
from ..permissions import workspace_access
from ..schemas import TaskType
from ..services.common import find_asset, page_data, search_query
from ..services.parameter_templates import change_template, create_template, resolve_template
from ..template_models import TrainingParameterTemplate as Template
from ..template_schemas import TemplateArchive, TemplateCreate, TemplateEdit, TemplateResolve
from .deps import Actor, Db, Expected, Page, PageSize, Search

router = APIRouter(prefix='/api/v1/workspaces/{workspace_id}/training-parameter-templates', tags=['训练参数模板'])


@router.get('')
def templates(workspace_id: str, request: Request, actor: Actor, db: Db, page: Page = 1,
              page_size: PageSize = 20, task_type: TaskType | None = None, trainer_id: Search = '',
              status: Literal['active', 'archived', 'all'] = 'active', q: Search = ''):
    workspace_access(db, actor, workspace_id, 'training.read')
    query = select(Template).where(Template.workspace_id == workspace_id)
    if task_type:
        query = query.where(Template.task_type == task_type)
    if trainer_id:
        query = query.where(Template.trainer_id == trainer_id)
    if status != 'all':
        query = query.where(Template.archived == (status == 'archived'))
    rows, pagination = page_data(db, search_query(query, q, Template.name), page, page_size)
    return response(request, rows, pagination=pagination)


@router.post('', status_code=201)
def create(workspace_id: str, payload: TemplateCreate, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, 'training.write')
    return response(request, create_template(db, actor, workspace_id, payload))


@router.patch('/{template_id}')
def edit(workspace_id: str, template_id: str, payload: TemplateEdit, request: Request,
         actor: Actor, db: Db, expected: Expected):
    workspace_access(db, actor, workspace_id, 'training.write')
    item = find_asset(db, Template, workspace_id, template_id)
    return response(request, change_template(db, actor, item, payload, expected))


@router.post('/{template_id}/archive')
def archive(workspace_id: str, template_id: str, payload: TemplateArchive, request: Request,
            actor: Actor, db: Db, expected: Expected):
    workspace_access(db, actor, workspace_id, 'training.write')
    item = find_asset(db, Template, workspace_id, template_id)
    return response(request, change_template(db, actor, item, payload, expected))


@router.post('/{template_id}/resolve')
def resolve(workspace_id: str, template_id: str, payload: TemplateResolve, request: Request,
            actor: Actor, db: Db, expected: Expected):
    workspace_access(db, actor, workspace_id, 'training.write')
    item = find_asset(db, Template, workspace_id, template_id)
    return response(request, resolve_template(db, actor, item, payload.model_version_id, expected))
