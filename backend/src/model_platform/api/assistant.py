from fastapi import APIRouter, Request
from sqlalchemy import func, select

from ..assistant_models import AssistantRequest
from ..assistant_schemas import AIPolicyInput, AssistantApply, AssistantConfirm, AssistantPrepare
from ..errors import Problem, response
from ..outputs import Envelope
from ..permissions import workspace_access, effective_policy
from ..services.assistant_policy import policy_view, public_connections, save_policy
from ..services.assistant_requests import cancel, confirm, find_request, prepare, request_view, visible
from ..services.assistant_requests import apply as apply_result
from ..services.assistant_sources import permission
from .deps import Actor, Db, Page, PageSize

router = APIRouter(tags=["智能辅助"])
base = "/api/v1/workspaces/{workspace_id}"


@router.get(base + "/assistant-policy", response_model=Envelope[dict])
def read_policy(workspace_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "assistants.use")
    return response(request, policy_view(db, workspace_id))


@router.post(base + "/assistant-policy", response_model=Envelope[dict])
def update_policy(workspace_id: str, payload: AIPolicyInput, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "members.manage")
    return response(request, save_policy(db, actor, workspace_id, payload))


@router.get(base + "/assistant-options", response_model=Envelope[dict])
def options(workspace_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "assistants.use")
    policy = policy_view(db, workspace_id)
    space = workspace_access(db, actor, workspace_id, "assistants.use")
    manager = (actor.is_admin or space.owner_id == actor.id) and "members.manage" in effective_policy(db, actor)[0]
    return response(request, {"policy": policy, "connections": public_connections(db, None if manager else policy["connection_ids"]),
        "purposes": [{"key": "annotation", "name": "智能标注"}, {"key": "parameters", "name": "智能参数"},
                     {"key": "logs", "name": "智能解释"}]})


@router.get(base + "/assistant-requests")
def requests_list(workspace_id: str, request: Request, actor: Actor, db: Db,
                  page: Page = 1, page_size: PageSize = 20,
                  status: str = "", purpose: str = ""):
    workspace_access(db, actor, workspace_id, "assistants.use")
    query = select(AssistantRequest).where(AssistantRequest.workspace_id == workspace_id)
    actions = effective_policy(db, actor)[0]
    purposes = (["annotation"] if "datasets.read" in actions else []) + (["parameters", "logs"] if "training.read" in actions else [])
    query = query.where(AssistantRequest.purpose.in_(purposes))
    if not actor.is_admin:
        # 普通成员只看到自己的请求，避免跨成员读取他人预览与结果。
        query = query.where(AssistantRequest.created_by == actor.id)
    if status:
        query = query.where(AssistantRequest.status == status)
    if purpose:
        query = query.where(AssistantRequest.purpose == purpose)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(AssistantRequest.created_at.desc(), AssistantRequest.id)
                       .offset((page - 1) * page_size).limit(page_size)).all()
    return response(request, [request_view(db, item) for item in items],
                    pagination={"page": page, "page_size": page_size, "total": total})


@router.post(base + "/assistant-requests", status_code=201, response_model=Envelope[dict])
def create_request(workspace_id: str, payload: AssistantPrepare, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "assistants.use")
    return response(request, prepare(db, request.app.state.settings, actor, workspace_id, payload))


@router.get(base + "/assistant-requests/{request_id}", response_model=Envelope[dict])
def get_request(workspace_id: str, request_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "assistants.use")
    item = find_request(db, workspace_id, request_id)
    if not visible(db, actor, workspace_id, item):
        raise Problem(403, "FORBIDDEN", "无权查看其他成员的智能请求")
    permission(db, actor, workspace_id, item.purpose)
    return response(request, request_view(db, item))


@router.post(base + "/assistant-requests/{request_id}/confirm", response_model=Envelope[dict])
def confirm_request(workspace_id: str, request_id: str, payload: AssistantConfirm, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "assistants.use")
    return response(request, confirm(db, actor, find_request(db, workspace_id, request_id), payload.input_digest,
                                     settings=request.app.state.settings))


@router.post(base + "/assistant-requests/{request_id}/cancel", response_model=Envelope[dict])
def cancel_request(workspace_id: str, request_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "assistants.use")
    return response(request, cancel(db, actor, find_request(db, workspace_id, request_id)))


@router.post(base + "/assistant-requests/{request_id}/apply", response_model=Envelope[dict])
def apply_request(workspace_id: str, request_id: str, payload: AssistantApply, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "assistants.use")
    return response(request, apply_result(db, actor, find_request(db, workspace_id, request_id), payload))
