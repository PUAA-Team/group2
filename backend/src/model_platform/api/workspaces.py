from fastapi import APIRouter, Request
from sqlalchemy import func, select

from ..database import new_id
from ..errors import Problem, response
from ..models import AuditEvent, Membership, User, Workspace
from ..outputs import AccessOut, AuditOut, Envelope, MemberOut, MemberSummaryOut, PageEnvelope, WorkspaceOut
from ..permissions import effective_policy, require_action, visible_workspaces, workspace_access, WRITE_SUFFIXES
from ..schemas import MemberInput, WorkspaceCreate
from ..services.common import audit, commit, page_data, serialize
from .deps import Actor, Db, Page, PageSize

router = APIRouter(prefix="/api/v1/workspaces", tags=["工作空间"])


@router.get("", response_model=PageEnvelope[WorkspaceOut])
def list_workspaces(request: Request, actor: Actor, db: Db, page: Page = 1, page_size: PageSize = 20):
    items, pagination = page_data(db, visible_workspaces(db, actor), page, page_size)
    return response(request, items, pagination=pagination)


@router.post("", status_code=201, response_model=Envelope[WorkspaceOut])
def create_workspace(payload: WorkspaceCreate, request: Request, actor: Actor, db: Db):
    require_action(db, actor, "workspaces.create")
    workspace = Workspace(id=new_id("wsp"), owner_id=actor.id, **payload.model_dump())
    db.add(workspace)
    db.flush()
    db.add(Membership(workspace_id=workspace.id, user_id=actor.id, role="editor"))
    audit(db, actor, "workspaces.create", workspace.id, workspace.id)
    commit(db)
    return response(request, serialize(workspace))


@router.post("/{workspace_id}/members", response_model=Envelope[MemberOut])
def set_member(workspace_id: str, payload: MemberInput, request: Request, actor: Actor, db: Db):
    workspace = workspace_access(db, actor, workspace_id, "members.manage")
    user = db.get(User, payload.user_id) if payload.user_id else db.scalar(
        select(User).where(User.account == payload.account.lower()))
    if not user or not user.active:
        raise Problem(422, "VALIDATION_ERROR", "请选择启用的用户")
    if user.id == workspace.owner_id and payload.role != "editor":
        raise Problem(409, "CONFLICT", "所有者需要保留编辑角色")
    member = db.get(Membership, (workspace_id, user.id))
    if member:
        member.role = payload.role
    else:
        member = Membership(workspace_id=workspace_id, user_id=user.id, role=payload.role)
        db.add(member)
    audit(db, actor, "members.update", user.id, workspace_id)
    commit(db)
    return response(request, serialize(member))


@router.get("/{workspace_id}/members", response_model=PageEnvelope[MemberSummaryOut])
def list_members(workspace_id: str, request: Request, actor: Actor, db: Db,
                 page: Page = 1, page_size: PageSize = 20):
    workspace_access(db, actor, workspace_id, "members.manage")
    query = select(Membership, User).join(User, Membership.user_id == User.id).where(Membership.workspace_id == workspace_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(User.account).offset((page - 1) * page_size).limit(page_size)).all()
    items = [{**serialize(member), "account": user.account, "display_name": user.display_name,
              "active": user.active} for member, user in rows]
    return response(request, items, pagination={"page": page, "page_size": page_size, "total": total})


@router.get("/{workspace_id}/access", response_model=Envelope[AccessOut])
def access(workspace_id: str, request: Request, actor: Actor, db: Db):
    # 此接口只需成员身份，允许尚未分配资产权限的成员了解自己的授权。
    workspace = db.get(Workspace, workspace_id)
    member = db.get(Membership, (workspace_id, actor.id))
    if not workspace or (not actor.is_admin and not member):
        raise Problem(404, "NOT_FOUND", "工作空间不存在")
    actions, quota = effective_policy(db, actor)
    if not actor.is_admin and member.role == "viewer":
        actions = {action for action in actions if not action.endswith(WRITE_SUFFIXES)}
    if not actor.is_admin and workspace.owner_id != actor.id:
        actions.discard("members.manage")
    return response(request, {"actions": sorted(actions), "quota": quota,
                              "role": "admin" if actor.is_admin else member.role})


@router.get("/{workspace_id}/audit", response_model=PageEnvelope[AuditOut])
def list_audit(workspace_id: str, request: Request, actor: Actor, db: Db,
               page: Page = 1, page_size: PageSize = 20):
    workspace_access(db, actor, workspace_id, "audit.read")
    items, pagination = page_data(db, select(AuditEvent).where(AuditEvent.workspace_id == workspace_id), page, page_size)
    return response(request, items, pagination=pagination)
