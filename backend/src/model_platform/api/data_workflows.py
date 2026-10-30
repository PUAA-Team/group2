from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import func, select

from ..data_models import AnnotationBatch, DataOperation
from ..data_schemas import AnnotationInput, OperationInput, ResultInput, ReviewInput
from ..errors import response
from ..outputs import Envelope
from ..models import Dataset, DatasetVersion, Membership, User
from ..services.common import serialize
from ..permissions import workspace_access
from ..services.annotations import batch_detail, batch_view, create_batch, find_batch, publish_batch, review_results, save_result
from ..services.data_operations import candidate_source, cancel_operation, create_operation, find_operation, operation_view, publish_operation
from ..services.data_samples import image_sample, read_source, sample_page, source
from .deps import Actor, Db, Page, PageSize, Search

router = APIRouter(tags=["数据处理与标注"])
base = "/api/v1/workspaces/{workspace_id}"


@router.get(base + "/data-options", response_model=Envelope[dict])
def data_options(workspace_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.read")
    versions = [{**serialize(version), "name": dataset.name, "task_type": dataset.task_type}
        for dataset, version in db.execute(select(Dataset, DatasetVersion).join(DatasetVersion,
            DatasetVersion.dataset_id == Dataset.id).where(Dataset.workspace_id == workspace_id)
            .order_by(DatasetVersion.created_at.desc()).limit(500))]
    members = [{"id": user.id, "name": user.display_name} for user in db.scalars(select(User).join(
        Membership, Membership.user_id == User.id).where(Membership.workspace_id == workspace_id,
        Membership.role != "viewer", User.active.is_(True)).order_by(User.display_name))]
    return response(request, {"versions": versions, "members": members})


@router.get(base + "/dataset-versions/{version_id}/samples", response_model=Envelope[dict])
def samples(workspace_id: str, version_id: str, request: Request, actor: Actor, db: Db,
            page: Page = 1, page_size: PageSize = 20):
    workspace_access(db, actor, workspace_id, "datasets.read")
    dataset, version = source(db, workspace_id, version_id)
    return response(request, sample_page(request.app.state.settings, dataset, version, page, page_size))


@router.get(base + "/dataset-versions/{version_id}/images/{index}")
def image(workspace_id: str, version_id: str, index: int, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.read")
    dataset, version = source(db, workspace_id, version_id)
    content, media = image_sample(request.app.state.settings, dataset, version, index)
    return Response(content, media_type=media)


@router.get(base + "/dataset-versions/{version_id}/download")
def download(workspace_id: str, version_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.read")
    dataset, version = source(db, workspace_id, version_id)
    _, content = read_source(request.app.state.settings, dataset, version)
    return Response(content, media_type="application/octet-stream", headers={
        "Content-Disposition": f'attachment; filename="dataset-v{version.number}.{version.format}"'})


@router.get(base + "/annotation-batches")
def batches(workspace_id: str, request: Request, actor: Actor, db: Db,
            page: Page = 1, page_size: PageSize = 20, q: Search = ""):
    workspace_access(db, actor, workspace_id, "datasets.read")
    query = select(AnnotationBatch).where(AnnotationBatch.workspace_id == workspace_id)
    if q:
        query = query.where(AnnotationBatch.name.contains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(AnnotationBatch.created_at.desc(), AnnotationBatch.id)
                       .offset((page - 1) * page_size).limit(page_size)).all()
    data = []
    for item in items:
        dataset, version = source(db, workspace_id, item.version_id)
        data.append({**batch_view(db, item), "dataset_name": dataset.name, "version_number": version.number,
                     "task_type": dataset.task_type})
    return response(request, data, pagination={"page": page, "page_size": page_size, "total": total})


@router.post(base + "/annotation-batches", status_code=201, response_model=Envelope[dict])
def new_batch(workspace_id: str, payload: AnnotationInput, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.write")
    return response(request, create_batch(db, request.app.state.settings, actor, workspace_id, payload))


@router.get(base + "/annotation-batches/{batch_id}", response_model=Envelope[dict])
def get_batch(workspace_id: str, batch_id: str, request: Request, actor: Actor, db: Db,
              page: Page = 1, page_size: PageSize = 20):
    workspace_access(db, actor, workspace_id, "datasets.read")
    return response(request, batch_detail(db, request.app.state.settings, actor,
        find_batch(db, workspace_id, batch_id), page, page_size))


@router.post(base + "/annotation-batches/{batch_id}/results/{index}", response_model=Envelope[dict])
def result(workspace_id: str, batch_id: str, index: int, payload: ResultInput, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.write")
    return response(request, save_result(db, actor, find_batch(db, workspace_id, batch_id), index, payload))


@router.post(base + "/annotation-batches/{batch_id}/review", response_model=Envelope[dict])
def review(workspace_id: str, batch_id: str, payload: ReviewInput, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.write")
    return response(request, review_results(db, actor, find_batch(db, workspace_id, batch_id), payload))


@router.post(base + "/annotation-batches/{batch_id}/publish", response_model=Envelope[dict])
def publish(workspace_id: str, batch_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.write")
    return response(request, publish_batch(db, request.app.state.settings, actor, find_batch(db, workspace_id, batch_id)))


@router.get(base + "/data-operations")
def operations(workspace_id: str, request: Request, actor: Actor, db: Db,
               page: Page = 1, page_size: PageSize = 20, q: Search = "",
               kind: Annotated[str, Query(pattern="^(clean|split|augment|)$")] = ""):
    workspace_access(db, actor, workspace_id, "datasets.read")
    query = select(DataOperation).where(DataOperation.workspace_id == workspace_id)
    if q:
        query = query.where(DataOperation.name.contains(q, autoescape=True))
    if kind:
        query = query.where(DataOperation.kind == kind)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(DataOperation.created_at.desc(), DataOperation.id)
                       .offset((page - 1) * page_size).limit(page_size)).all()
    data = []
    for item in items:
        dataset, version = source(db, workspace_id, item.version_id)
        data.append({**operation_view(item), "dataset_name": dataset.name, "version_number": version.number})
    return response(request, data, pagination={"page": page, "page_size": page_size, "total": total})


@router.post(base + "/data-operations", status_code=201, response_model=Envelope[dict])
def new_operation(workspace_id: str, payload: OperationInput, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.write")
    return response(request, create_operation(db, actor, workspace_id, payload))


@router.get(base + "/data-operations/{operation_id}", response_model=Envelope[dict])
def get_operation(workspace_id: str, operation_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.read")
    item = find_operation(db, workspace_id, operation_id)
    dataset, version = source(db, workspace_id, item.version_id)
    return response(request, {**operation_view(item), "dataset_name": dataset.name, "dataset_id": dataset.id,
        "task_type": dataset.task_type, "version_number": version.number})


@router.post(base + "/data-operations/{operation_id}/cancel", response_model=Envelope[dict])
def cancel(workspace_id: str, operation_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.write")
    return response(request, cancel_operation(db, actor, find_operation(db, workspace_id, operation_id)))


@router.post(base + "/data-operations/{operation_id}/publish", response_model=Envelope[dict])
def publish_processed(workspace_id: str, operation_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "datasets.write")
    return response(request, publish_operation(db, request.app.state.settings, actor, find_operation(db, workspace_id, operation_id)))


@router.get(base + "/data-operations/{operation_id}/preview", response_model=Envelope[dict])
def candidate(workspace_id: str, operation_id: str, request: Request, actor: Actor, db: Db,
              candidate: Annotated[int, Query(ge=0)] = 0, page: Page = 1, page_size: PageSize = 20):
    workspace_access(db, actor, workspace_id, "datasets.read")
    dataset, version = candidate_source(db, request.app.state.settings,
        find_operation(db, workspace_id, operation_id), candidate)
    return response(request, sample_page(request.app.state.settings, dataset, version, page, page_size))


@router.get(base + "/data-operations/{operation_id}/images/{index}")
def candidate_image(workspace_id: str, operation_id: str, index: int, request: Request, actor: Actor, db: Db,
                    candidate: Annotated[int, Query(ge=0)] = 0):
    workspace_access(db, actor, workspace_id, "datasets.read")
    dataset, version = candidate_source(db, request.app.state.settings,
        find_operation(db, workspace_id, operation_id), candidate)
    content, media = image_sample(request.app.state.settings, dataset, version, index)
    return Response(content, media_type=media)
