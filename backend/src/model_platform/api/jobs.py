from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from ..database import new_id
from ..errors import Problem, response
from ..job_models import Execution, ExecutionEvent, Job, Project
from ..job_schemas import JobInput, ProjectInput
from ..models import Dataset, DatasetVersion, ModelAsset, ModelVersion
from ..permissions import workspace_access
from ..schemas import Input, TaskType
from pydantic import Field
from ..services.common import audit, commit, find_asset, page_data, revision_update, search_query, serialize
from ..services.dataset_files import controlled_path
from ..services.jobs import TERMINAL, action_for, create_job, get_job, inputs, job_view, stop_job, submit_job
from ..services.presets import seed_presets
from ..services.inference_contracts import inference_suggestion
from ..services.console import job_summary
from .deps import Actor, Db, Expected, Page, PageSize, Search

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["训练与执行"])


class PresetInput(Input):
    task_types: list[TaskType] = Field(default_factory=lambda: ["text_classification", "image_classification", "llm_sft"], min_length=1, max_length=3)


@router.post("/presets")
async def presets(workspace_id: str, payload: PresetInput, request: Request, actor: Actor, db: Db):
    return response(request, await seed_presets(db, request.app.state.settings, actor, workspace_id, payload.task_types))


@router.get("/job-options")
def job_options(workspace_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "models.read")
    workspace_access(db, actor, workspace_id, "datasets.read")
    models = []
    for version, model in db.execute(select(ModelVersion, ModelAsset).join(ModelAsset).where(ModelAsset.workspace_id == workspace_id).order_by(ModelVersion.created_at.desc()).limit(500)):
        item = {**serialize(version), "name": model.name, "task_type": model.task_type, "trainer_id": model.trainer_id}
        if model.trainer_id == "qwen-lora-v1" and version.status == "available":
            item["inference_suggestion"] = inference_suggestion(db, request.app.state.settings, workspace_id, version)
        models.append(item)
    datasets = [{**serialize(version), "name": dataset.name, "task_type": dataset.task_type} for version, dataset in db.execute(select(DatasetVersion, Dataset).join(Dataset).where(Dataset.workspace_id == workspace_id, DatasetVersion.status == "available").order_by(DatasetVersion.created_at.desc()).limit(500))]
    return response(request, {"models": models, "datasets": datasets})


@router.get("/projects")
def projects(workspace_id: str, request: Request, actor: Actor, db: Db, page: Page = 1, page_size: PageSize = 20, q: Search = ""):
    workspace_access(db, actor, workspace_id, "training.read")
    data, pagination = page_data(db, search_query(select(Project).where(Project.workspace_id == workspace_id), q, Project.name), page, page_size)
    return response(request, data, pagination=pagination)


@router.post("/projects", status_code=201)
def new_project(workspace_id: str, payload: ProjectInput, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "training.write")
    item = Project(id=new_id("prj"), workspace_id=workspace_id, name=payload.name, created_by=actor.id)
    db.add(item); audit(db, actor, "projects.create", item.id, workspace_id); commit(db)
    return response(request, serialize(item))


@router.get("/jobs")
def jobs(workspace_id: str, request: Request, actor: Actor, db: Db, kind: Literal["train", "evaluate", "service"] = "train", page: Page = 1, page_size: PageSize = 20, q: Search = "", project_id: str | None = None,
         status: Literal["draft", "queued", "preparing", "running", "ready", "stopping", "stopped", "cancelled", "succeeded", "failed"] | None = None,
         device_kind: Literal["cpu", "cuda"] | None = None, task_type: TaskType | None = None, sort: Literal["newest", "oldest"] = "newest"):
    workspace_access(db, actor, workspace_id, action_for(kind))
    query = select(Job).where(Job.workspace_id == workspace_id, Job.kind == kind)
    if project_id:
        query = query.where(Job.project_id == project_id)
    if status:
        query = query.where(Job.status == status)
    if device_kind:
        query = query.where(Job.device_kind == device_kind)
    if task_type:
        query = query.join(ModelVersion, ModelVersion.id == Job.model_version_id).join(ModelAsset, ModelAsset.id == ModelVersion.model_id).where(ModelAsset.task_type == task_type)
    query = query.order_by(Job.created_at.desc() if sort == "newest" else Job.created_at.asc())
    data, pagination = page_data(db, search_query(query, q, Job.name), page, page_size)
    return response(request, [job_summary(db, db.get(Job, row["id"])) for row in data], pagination=pagination)


@router.post("/jobs", status_code=201)
def new_job(workspace_id: str, payload: JobInput, request: Request, actor: Actor, db: Db):
    return response(request, job_view(db, create_job(db, actor, workspace_id, payload)))


@router.get("/jobs/{job_id}")
def detail(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db):
    return response(request, job_view(db, get_job(db, actor, workspace_id, job_id)))


@router.patch("/jobs/{job_id}")
def edit_job(workspace_id: str, job_id: str, payload: JobInput, request: Request, actor: Actor, db: Db, expected: Expected):
    job = get_job(db, actor, workspace_id, job_id, True)
    workspace_access(db, actor, workspace_id, action_for(payload.kind, True))
    if job.status != "draft":
        raise Problem(409, "INVALID_STATE", "只有草稿可以修改")
    inputs(db, workspace_id, payload)
    revision_update(db, job, payload.model_dump(mode="json"), expected)
    audit(db, actor, "jobs.update", job.id, workspace_id); commit(db)
    return response(request, job_view(db, job))


@router.post("/jobs/{job_id}/submit")
def submit(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db, expected: Expected):
    job = get_job(db, actor, workspace_id, job_id, True)
    return response(request, job_view(db, submit_job(db, request.app.state.settings, actor, job, expected)))


@router.post("/jobs/{job_id}/stop")
def stop(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db):
    return response(request, job_view(db, stop_job(db, actor, get_job(db, actor, workspace_id, job_id, True))))


@router.post("/jobs/{job_id}/retry", status_code=201)
def retry(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db):
    job = get_job(db, actor, workspace_id, job_id, True)
    if job.status not in TERMINAL:
        raise Problem(409, "INVALID_STATE", "结束后的任务可以重跑")
    payload = JobInput(**{key: getattr(job, key) for key in JobInput.model_fields})
    payload.name = (job.name[:92] + " · 重跑")
    return response(request, job_view(db, create_job(db, actor, workspace_id, payload)))


@router.get("/jobs/{job_id}/events")
def events(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db, after: Annotated[int, Query(ge=0)] = 0):
    job = get_job(db, actor, workspace_id, job_id)
    execution = db.scalar(select(Execution).where(Execution.job_id == job.id))
    rows = db.scalars(select(ExecutionEvent).where(ExecutionEvent.execution_id == execution.id, ExecutionEvent.seq > after).order_by(ExecutionEvent.seq).limit(200)).all() if execution else []
    return response(request, [serialize(row) for row in rows])


@router.get("/jobs/{job_id}/artifact")
def artifact(workspace_id: str, job_id: str, request: Request, actor: Actor, db: Db):
    job = get_job(db, actor, workspace_id, job_id)
    if not job.artifact_key or job.status != "succeeded":
        raise Problem(404, "NOT_FOUND", "没有可用模型产物")
    path = controlled_path(request.app.state.settings, job.artifact_key)
    if not path.is_file():
        raise Problem(503, "NOT_READY", "产物文件缺失")
    return FileResponse(path, filename=f"{job.id}.zip", media_type="application/zip", headers={"X-Content-SHA256": job.artifact_sha256})
