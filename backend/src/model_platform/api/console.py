from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..errors import Problem, response
from ..job_models import Execution, ExecutionEvent
from ..schemas import TaskType
from ..permissions import workspace_access
from ..services.dataset_files import parse_samples
from ..services.console import dataset_catalog, model_catalog, my_jobs, overview, project_catalog
from ..services.jobs import get_job
from .deps import Actor, Db, Page, PageSize, Search

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["控制台概览与目录"])


@router.get("/overview")
def workspace_overview(workspace_id: str, request: Request, actor: Actor, db: Db):
    return response(request, overview(db, actor, workspace_id))


@router.get("/my-jobs")
def personal_jobs(workspace_id: str, request: Request, actor: Actor, db: Db, page: Page = 1, page_size: PageSize = 20):
    rows, pagination = my_jobs(db, actor, workspace_id, page, page_size)
    return response(request, rows, pagination=pagination)


@router.get("/model-catalog")
def models(workspace_id: str, request: Request, actor: Actor, db: Db, q: Search = "", task_type: TaskType | None = None,
           category: Literal["all", "prebuilt", "network", "trained"] = "all", page: Page = 1, page_size: PageSize = 20,
           status: Literal['all', 'active', 'archived'] = 'all'):
    rows, pagination = model_catalog(db, actor, workspace_id, q, task_type, category, page, page_size, status)
    return response(request, rows, pagination=pagination)


@router.get("/dataset-catalog")
def datasets(workspace_id: str, request: Request, actor: Actor, db: Db, q: Search = "", task_type: TaskType | None = None,
             page: Page = 1, page_size: PageSize = 20, status: Literal['all', 'active', 'archived'] = 'all',
             version_status: Literal['available', 'needs_annotation', 'unversioned'] | None = None):
    rows, pagination = dataset_catalog(db, actor, workspace_id, q, task_type, page, page_size, status, version_status)
    return response(request, rows, pagination=pagination)


@router.get("/project-catalog")
def projects(workspace_id: str, request: Request, actor: Actor, db: Db, q: Search = "", page: Page = 1, page_size: PageSize = 20,
             status: Literal['all', 'active', 'archived'] = 'all'):
    rows, pagination = project_catalog(db, actor, workspace_id, q, page, page_size, status)
    return response(request, rows, pagination=pagination)


@router.get("/jobs/{job_id}/logs")
def download_logs(workspace_id: str, job_id: str, actor: Actor, db: Db):
    job = get_job(db, actor, workspace_id, job_id)
    execution = db.scalar(select(Execution).where(Execution.job_id == job.id))

    def content():
        if execution:
            query = select(ExecutionEvent).where(ExecutionEvent.execution_id == execution.id, ExecutionEvent.type == "log").order_by(ExecutionEvent.seq).execution_options(yield_per=100)
            for event in db.scalars(query):
                yield (str(event.payload.get("message", "")) + "\n").encode("utf-8")

    return StreamingResponse(content(), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{job.id}.log"'})
@router.post("/dataset-previews")
async def preview_upload(workspace_id: str, request: Request, actor: Actor, db: Db,
                         task_type: TaskType = Form(), file: UploadFile = File(),
                         column_mapping: Annotated[str | None, Form(max_length=16384)] = None):
    workspace_access(db, actor, workspace_id, "datasets.write")
    settings = request.app.state.settings
    from ..services.platform_settings import dataset_limits
    settings = dataset_limits(db, settings)
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise Problem(413, "FILE_TOO_LARGE", "文件超过大小限制")
    from ..services.dataset_mapping import decode_mapping, normalize_upload
    filename, normalized, provenance, rows, metadata = normalize_upload(content, task_type, file.filename,
        settings.max_samples, decode_mapping(column_mapping))
    if len(normalized) > settings.max_upload_bytes:
        raise Problem(413, "FILE_TOO_LARGE", "标准化文件超过大小限制")
    return response(request, {**metadata, "samples": rows[:50], "filename": filename, "provenance": provenance})


@router.post('/dataset-column-inspection')
async def inspect_upload(workspace_id: str, request: Request, actor: Actor, db: Db,
                         task_type: TaskType = Form(), file: UploadFile = File()):
    from ..services.dataset_mapping import inspect_columns
    from ..services.platform_settings import dataset_limits
    workspace_access(db, actor, workspace_id, 'datasets.write')
    settings = dataset_limits(db, request.app.state.settings)
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise Problem(413, 'FILE_TOO_LARGE', '文件超过大小限制')
    return response(request, inspect_columns(content, task_type, file.filename, settings.max_samples))
