from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select

from ..compute_models import ComputeNode, Enrollment
from ..compute_outputs import EnrollmentOut, EnrollmentStatus, NodeOut
from ..compute_schemas import EnrollmentInput, LocalWorkerInput, NodePatch
from ..database import aware, new_id, utcnow
from ..errors import Problem, response
from ..outputs import Envelope, PageEnvelope
from ..permissions import require_admin, workspace_access
from ..services.common import audit, commit, search_query
from ..services.compute import create_enrollment, get_visible_node, lock_node, node_busy, update_node
from ..services.compute_views import node_view
from ..services.local_worker import configured_runtimes, local_allowed, start_local_worker, stop_local_worker
from .deps import Actor, Db, Expected, Page, PageSize, Search

router = APIRouter(prefix="/api/v1", tags=["计算资源"])


def list_nodes(db, settings, query, page, page_size):
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    nodes = db.scalars(query.order_by(ComputeNode.created_at, ComputeNode.id).offset((page - 1) * page_size).limit(page_size)).all()
    return [node_view(db, node, settings) for node in nodes], {"page": page, "page_size": page_size, "total": total}


@router.get("/admin/nodes", response_model=PageEnvelope[NodeOut])
def admin_nodes(request: Request, actor: Actor, db: Db, page: Page = 1, page_size: PageSize = 20, q: Search = ""):
    require_admin(db, actor, "resources.read")
    data, pagination = list_nodes(db, request.app.state.settings, search_query(select(ComputeNode), q, ComputeNode.name), page, page_size)
    return response(request, data, pagination=pagination)


@router.get("/workspaces/{workspace_id}/resources", response_model=PageEnvelope[NodeOut])
def workspace_nodes(workspace_id: str, request: Request, actor: Actor, db: Db,
                    page: Page = 1, page_size: PageSize = 20, q: Search = ""):
    workspace_access(db, actor, workspace_id, "resources.read")
    query = search_query(select(ComputeNode).where(ComputeNode.workspace_id == workspace_id), q, ComputeNode.name)
    data, pagination = list_nodes(db, request.app.state.settings, query, page, page_size)
    return response(request, data, pagination=pagination)


@router.post("/admin/enrollments", status_code=201, response_model=Envelope[EnrollmentOut])
def admin_enroll(payload: EnrollmentInput, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "resources.manage")
    return response(request, create_enrollment(db, request.app.state.settings, actor, payload))


@router.post("/workspaces/{workspace_id}/enrollments", status_code=201, response_model=Envelope[EnrollmentOut])
def workspace_enroll(workspace_id: str, payload: EnrollmentInput, request: Request, actor: Actor, db: Db):
    if workspace_id != payload.workspace_id:
        raise Problem(422, "VALIDATION_ERROR", "空间与申请不一致")
    return response(request, create_enrollment(db, request.app.state.settings, actor, payload))


@router.get("/resources/enrollments/{enrollment_id}", response_model=Envelope[EnrollmentStatus])
def enrollment_status(enrollment_id: str, request: Request, actor: Actor, db: Db):
    item = db.get(Enrollment, enrollment_id)
    if not item:
        raise Problem(404, "NOT_FOUND", "接入申请不存在")
    workspace_access(db, actor, item.workspace_id, "resources.manage")
    if item.created_by != actor.id and not actor.is_admin:
        raise Problem(404, "NOT_FOUND", "接入申请不存在")
    status = "已撤销" if item.revoked_at else "已接入" if item.consumed_node_id else "已过期" if aware(item.expires_at) <= utcnow() else "等待连接"
    return response(request, {"id": item.id, "status": status, "node_id": item.consumed_node_id,
                              "expires_at": aware(item.expires_at).isoformat()})


@router.post("/resources/enrollments/{enrollment_id}/revoke")
def revoke_enrollment(enrollment_id: str, request: Request, actor: Actor, db: Db):
    item = db.get(Enrollment, enrollment_id)
    if not item:
        raise Problem(404, "NOT_FOUND", "接入申请不存在")
    workspace_access(db, actor, item.workspace_id, "resources.manage")
    if item.created_by != actor.id and not actor.is_admin:
        raise Problem(404, "NOT_FOUND", "接入申请不存在")
    item.revoked_at = utcnow()
    audit(db, actor, "resources.enrollment.revoke", item.id, item.workspace_id)
    commit(db)
    return response(request, {"revoked": True})


@router.get("/resources/nodes/{node_id}", response_model=Envelope[NodeOut])
def get_node(node_id: str, request: Request, output: Response, actor: Actor, db: Db):
    node = get_visible_node(db, actor, node_id, "resources.read")
    output.headers["ETag"] = f'"{node.revision}"'
    return response(request, node_view(db, node, request.app.state.settings))


@router.patch("/resources/nodes/{node_id}", response_model=Envelope[NodeOut])
def patch_node(node_id: str, payload: NodePatch, request: Request, actor: Actor, db: Db, expected: Expected):
    node = get_visible_node(db, actor, node_id, "resources.manage")
    return response(request, update_node(db, request.app.state.settings, actor, node, payload, expected))


@router.post("/resources/nodes/{node_id}/probe")
def probe(node_id: str, request: Request, actor: Actor, db: Db):
    node = get_visible_node(db, actor, node_id, "resources.manage")
    if node.revoked:
        raise Problem(409, "CONFLICT", "已撤销节点不能探测")
    node.probe_request_id = new_id("prb")
    audit(db, actor, "resources.probe", node.id, node.workspace_id)
    commit(db)
    return response(request, {"request_id": node.probe_request_id, "status": "等待 Worker 回传"})


@router.post("/resources/nodes/{node_id}/revoke")
def revoke(node_id: str, request: Request, actor: Actor, db: Db):
    node = get_visible_node(db, actor, node_id, "resources.manage")
    lock_node(db, node)
    if node_busy(db, node):
        raise Problem(409, "CONFLICT", "节点仍有执行，请先停止并确认结束")
    node.revoked, node.enabled = True, False
    node.revision += 1
    audit(db, actor, "resources.revoke", node.id, node.workspace_id)
    commit(db)
    return response(request, {"revoked": True})


@router.get("/admin/worker-runtimes")
def runtimes(request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "resources.manage")
    return response(request, {"local_enabled": local_allowed(request), "runtimes": configured_runtimes(request.app.state.settings)})


@router.post("/admin/local-worker", status_code=202)
def local_start(payload: LocalWorkerInput, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "resources.manage")
    workspace_access(db, actor, payload.workspace_id, "resources.manage")
    if not local_allowed(request):
        raise Problem(403, "FORBIDDEN", "本机快捷接入未开放")
    return response(request, start_local_worker(db, request.app.state.settings, actor, payload))


@router.post("/admin/local-worker/stop", status_code=202)
def local_stop(request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "resources.manage")
    if not local_allowed(request):
        raise Problem(403, "FORBIDDEN", "本机快捷控制未开放")
    return response(request, stop_local_worker(db, request.app.state.settings, actor))
