from typing import Annotated

from fastapi import APIRouter, File, Query, Request, Response, UploadFile
from sqlalchemy import select

from ..database import new_id
from ..errors import Problem, response
from ..models import Dataset, DatasetVersion
from ..outputs import DatasetOut, DatasetVersionOut, Envelope, PageEnvelope, PreviewOut
from ..permissions import require_action, workspace_access
from ..schemas import DatasetCreate, DatasetPatch
from ..services.common import audit, commit, find_asset, page_data, revision_update, search_query, serialize
from ..services.datasets import preview, store_version
from .deps import Actor, Db, Expected, Page, PageSize, Search

router = APIRouter(tags=["数据资产"])
base = "/api/v1/workspaces/{workspace_id}/datasets"


@router.get("/api/v1/dataset-templates/image-classification")
def image_template(actor: Actor, db: Db):
    from ..services.presets import preset_content
    require_action(db, actor, "datasets.read")
    filename, content = preset_content("image_classification")
    return Response(content, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="image-template.zip"'})


@router.get(base, response_model=PageEnvelope[DatasetOut])
def list_datasets(workspace_id: str, request: Request, actor: Actor, db: Db,
                  page: Page = 1, page_size: PageSize = 20, q: Search = ""):
    workspace_access(db, actor, workspace_id, "datasets.read")
    query = select(Dataset).where(Dataset.workspace_id == workspace_id)
    data, pagination = page_data(db, search_query(query, q, Dataset.name), page, page_size)
    return response(request, data, pagination=pagination)


@router.post(base, status_code=201, response_model=Envelope[DatasetOut])
def create_dataset(workspace_id: str, payload: DatasetCreate, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.write")
    dataset = Dataset(id=new_id("dat"), workspace_id=workspace_id, **payload.model_dump())
    db.add(dataset)
    audit(db, actor, "datasets.create", dataset.id, workspace_id)
    commit(db)
    return response(request, serialize(dataset))


@router.get(base + "/{dataset_id}", response_model=Envelope[DatasetOut])
def get_dataset(workspace_id: str, dataset_id: str, request: Request, output: Response, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.read")
    dataset = find_asset(db, Dataset, workspace_id, dataset_id)
    output.headers["ETag"] = f'"{dataset.revision}"'
    return response(request, serialize(dataset))


@router.patch(base + "/{dataset_id}", response_model=Envelope[DatasetOut])
def patch_dataset(workspace_id: str, dataset_id: str, payload: DatasetPatch, request: Request,
                  output: Response, actor: Actor, db: Db, expected: Expected):
    workspace_access(db, actor, workspace_id, "datasets.write")
    dataset = find_asset(db, Dataset, workspace_id, dataset_id)
    revision_update(db, dataset, payload.model_dump(exclude_unset=True), expected)
    audit(db, actor, "datasets.update", dataset.id, workspace_id)
    commit(db)
    output.headers["ETag"] = f'"{dataset.revision}"'
    return response(request, serialize(dataset))


@router.get(base + "/{dataset_id}/versions", response_model=PageEnvelope[DatasetVersionOut])
def list_versions(workspace_id: str, dataset_id: str, request: Request, actor: Actor, db: Db,
                  page: Page = 1, page_size: PageSize = 20):
    workspace_access(db, actor, workspace_id, "datasets.read")
    find_asset(db, Dataset, workspace_id, dataset_id)
    data, pagination = page_data(db, select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id), page, page_size)
    return response(request, data, pagination=pagination)


@router.post(base + "/{dataset_id}/versions", status_code=201, response_model=Envelope[DatasetVersionOut])
async def upload_version(workspace_id: str, dataset_id: str, request: Request, actor: Actor, db: Db,
                         file: Annotated[UploadFile, File()]):
    workspace_access(db, actor, workspace_id, "datasets.write")
    dataset = find_asset(db, Dataset, workspace_id, dataset_id)
    version = await store_version(db, request.app.state.settings, actor, dataset, file)
    return response(request, serialize(version))


@router.get(base + "/{dataset_id}/versions/{version_id}/preview", response_model=Envelope[PreviewOut])
def sample_preview(workspace_id: str, dataset_id: str, version_id: str, request: Request,
                   actor: Actor, db: Db, limit: Annotated[int, Query(ge=1, le=50)] = 10):
    workspace_access(db, actor, workspace_id, "datasets.read")
    dataset = find_asset(db, Dataset, workspace_id, dataset_id)
    version = db.scalar(select(DatasetVersion).where(DatasetVersion.id == version_id,
                                                     DatasetVersion.dataset_id == dataset_id))
    if version is None:
        raise Problem(404, "NOT_FOUND", "数据版本不存在")
    return response(request, preview(request.app.state.settings, dataset, version, limit))
