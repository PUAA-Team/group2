from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from ..database import new_id
from ..errors import response
from ..models import ModelAsset, ModelVersion
from ..outputs import Envelope, ModelOut, ModelVersionOut, PageEnvelope, TemplateOut
from ..permissions import workspace_access
from ..schemas import ModelCreate, ModelPatch, ModelVersionCreate
from ..services.assets import TRAINERS, check_trainer
from ..services.common import audit, commit, find_asset, page_data, revision_update, search_query, serialize
from .deps import Actor, Db, Expected, Page, PageSize, Search

router = APIRouter(tags=["模型资产"])
base = "/api/v1/workspaces/{workspace_id}/models"


@router.get("/api/v1/trainer-templates", response_model=Envelope[list[TemplateOut]])
def templates(request: Request, actor: Actor):
    return response(request, TRAINERS)


@router.get(base, response_model=PageEnvelope[ModelOut])
def list_models(workspace_id: str, request: Request, actor: Actor, db: Db,
                page: Page = 1, page_size: PageSize = 20, q: Search = ""):
    workspace_access(db, actor, workspace_id, "models.read")
    query = select(ModelAsset).where(ModelAsset.workspace_id == workspace_id)
    data, pagination = page_data(db, search_query(query, q, ModelAsset.name), page, page_size)
    return response(request, data, pagination=pagination)


@router.post(base, status_code=201, response_model=Envelope[ModelOut])
def create_model(workspace_id: str, payload: ModelCreate, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "models.write")
    check_trainer(payload.task_type, payload.trainer_id)
    model = ModelAsset(id=new_id("mdl"), workspace_id=workspace_id, **payload.model_dump())
    db.add(model)
    audit(db, actor, "models.create", model.id, workspace_id)
    commit(db)
    return response(request, serialize(model))


@router.get(base + "/{model_id}", response_model=Envelope[ModelOut])
def get_model(workspace_id: str, model_id: str, request: Request, output: Response, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "models.read")
    model = find_asset(db, ModelAsset, workspace_id, model_id)
    output.headers["ETag"] = f'"{model.revision}"'
    return response(request, serialize(model))


@router.patch(base + "/{model_id}", response_model=Envelope[ModelOut])
def patch_model(workspace_id: str, model_id: str, payload: ModelPatch, request: Request,
                output: Response, actor: Actor, db: Db, expected: Expected):
    workspace_access(db, actor, workspace_id, "models.write")
    model = find_asset(db, ModelAsset, workspace_id, model_id)
    revision_update(db, model, payload.model_dump(exclude_unset=True), expected)
    audit(db, actor, "models.update", model.id, workspace_id)
    commit(db)
    output.headers["ETag"] = f'"{model.revision}"'
    return response(request, serialize(model))


@router.get(base + "/{model_id}/versions", response_model=PageEnvelope[ModelVersionOut])
def list_versions(workspace_id: str, model_id: str, request: Request, actor: Actor, db: Db,
                  page: Page = 1, page_size: PageSize = 20):
    workspace_access(db, actor, workspace_id, "models.read")
    find_asset(db, ModelAsset, workspace_id, model_id)
    data, pagination = page_data(db, select(ModelVersion).where(ModelVersion.model_id == model_id), page, page_size)
    return response(request, data, pagination=pagination)


@router.post(base + "/{model_id}/versions", status_code=201, response_model=Envelope[ModelVersionOut])
def create_version(workspace_id: str, model_id: str, payload: ModelVersionCreate,
                   request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "models.write")
    find_asset(db, ModelAsset, workspace_id, model_id)
    version = ModelVersion(id=new_id("mvr"), model_id=model_id, created_by=actor.id, **payload.model_dump())
    db.add(version)
    audit(db, actor, "model_versions.create", version.id, workspace_id)
    commit(db)
    return response(request, serialize(version))
