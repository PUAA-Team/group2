from fastapi import APIRouter, Request
from sqlalchemy import select

from ..errors import response
from ..job_models import Job, Project
from ..job_schemas import ProjectArchive, ProjectPatch
from ..permissions import workspace_access
from ..services.common import audit, commit, find_asset, revision_update, serialize
from ..services.console import job_summary, project_rows
from .deps import Actor, Db, Expected

router = APIRouter(prefix='/api/v1/workspaces/{workspace_id}/projects', tags=['训练项目'])


@router.get('/{project_id}')
def detail(workspace_id: str, project_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, 'training.read')
    project = find_asset(db, Project, workspace_id, project_id)
    value = project_rows(db, [serialize(project)])[0]
    value['recent_jobs'] = [job_summary(db, job) for job in db.scalars(select(Job).where(
        Job.project_id == project.id, Job.kind == 'train').order_by(Job.created_at.desc(), Job.id.desc()).limit(10))]
    return response(request, value)


@router.patch('/{project_id}')
def edit(workspace_id: str, project_id: str, payload: ProjectPatch, request: Request,
         actor: Actor, db: Db, expected: Expected):
    workspace_access(db, actor, workspace_id, 'training.write')
    project = find_asset(db, Project, workspace_id, project_id)
    revision_update(db, project, payload.model_dump(exclude_unset=True), expected)
    audit(db, actor, 'projects.update', project.id, workspace_id); commit(db)
    return response(request, serialize(project))


@router.post('/{project_id}/archive')
def archive(workspace_id: str, project_id: str, payload: ProjectArchive, request: Request,
            actor: Actor, db: Db, expected: Expected):
    workspace_access(db, actor, workspace_id, 'training.write')
    project = find_asset(db, Project, workspace_id, project_id)
    revision_update(db, project, {'archived': payload.archived}, expected)
    audit(db, actor, 'projects.archive' if payload.archived else 'projects.restore', project.id, workspace_id); commit(db)
    return response(request, serialize(project))
