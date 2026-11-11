from typing import Literal

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ..errors import response
from ..permissions import require_admin
from ..services.reports import audit_csv, evaluation_csv, evaluation_summary
from .catalog_filters import Filters
from .deps import Actor, Db, Search

router = APIRouter(prefix='/api/v1', tags=['审计与评估报告'])


@router.get('/admin/audit-export')
def export_audit(request: Request, actor: Actor, db: Db, filters: Filters, q: Search = '', space: Search = '',
                 status: Literal['', 'success', 'failure'] = ''):
    require_admin(db, actor, 'audit.read')
    content = audit_csv(db, actor, q, space, status, filters)
    return Response(content, media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="audit.csv"'})


@router.get('/workspaces/{workspace_id}/jobs/{job_id}/evaluation-summary')
def summary(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db):
    return response(request, evaluation_summary(db, actor, workspace_id, job_id))


@router.get('/workspaces/{workspace_id}/jobs/{job_id}/evaluation-report')
def export_evaluation(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db,
                      format: Literal['json', 'csv'] = 'json'):
    value = evaluation_summary(db, actor, workspace_id, job_id)
    headers = {'Content-Disposition': f'attachment; filename="evaluation-{job_id}.{format}"'}
    if format == 'json':
        return JSONResponse(value, headers=headers)
    return Response(evaluation_csv(value), media_type='text/csv; charset=utf-8', headers=headers)
