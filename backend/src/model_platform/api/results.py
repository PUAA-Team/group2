from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request

from ..errors import response
from ..services.result_views import compare_evaluations, call_history, call_statistics
from ..services.service_calls import rotate_key
from ..services.evaluation_errors import error_samples
from .deps import Actor, Db, Page, PageSize

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["评估与调用记录"])


@router.get("/evaluation-comparison")
def comparison(workspace_id: str, request: Request, actor: Actor, db: Db,
               ids: Annotated[list[str], Query(min_length=2, max_length=6)]):
    return response(request, compare_evaluations(db, actor, workspace_id, ids))


@router.get("/jobs/{job_id}/call-history")
def history(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db,
            page: Page = 1, page_size: PageSize = 20,
            status: Literal["pending", "succeeded", "failed"] | None = None):
    rows, pagination = call_history(db, actor, workspace_id, job_id, page, page_size, status)
    return response(request, rows, pagination=pagination)


@router.get("/jobs/{job_id}/call-statistics")
def statistics(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db):
    return response(request, call_statistics(db, actor, workspace_id, job_id))


@router.post("/service-keys/{key_id}/rotate")
def rotate(workspace_id: str, key_id: str, request: Request, actor: Actor, db: Db):
    return response(request, rotate_key(db, actor, workspace_id, key_id))


@router.get("/jobs/{job_id}/error-samples")
def errors(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db,
           page: Page = 1, page_size: PageSize = 20):
    return response(request, error_samples(db, request.app.state.settings, actor, workspace_id, job_id, page, page_size))
