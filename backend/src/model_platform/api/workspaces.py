from fastapi import APIRouter, Request
from sqlalchemy import func, select

from ..administration_schemas import WorkspaceInviteInput, WorkspaceJoinInput, WorkspaceJoinReviewInput
from ..database import new_id
from ..errors import Problem, response
from ..models import AuditEvent, Membership, User, Workspace
from ..outputs import AccessOut, AuditOut, Envelope, MemberOut, MemberSummaryOut, PageEnvelope, WorkspaceOut
from ..permissions import (
    ANNOTATOR_ACTIONS,
    WRITE_SUFFIXES,
    effective_policy,
    is_workspace_admin,
    require_action,
    visible_workspaces,
    workspace_access,
    workspace_effective_quota,
)
from ..schemas import MemberInput, WorkspaceCreate, WorkspaceOwnerTransfer
from ..services.common import audit, commit, page_data, revision_update, serialize
from ..services.workspace_invites import (
    create_workspace_invite,
    join_workspace_by_code,
    list_join_requests,
    list_workspace_invites,
    review_join_request,
    revoke_workspace_invite,
)
from ..services.workspace_lifecycle import delete_workspace
from .deps import Actor, Db, Expected, Page, PageSize

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


@router.post("/join")
def join_workspace(payload: WorkspaceJoinInput, request: Request, actor: Actor, db: Db):
    return response(request, join_workspace_by_code(db, actor, payload.code))


@router.delete("/{workspace_id}")
def remove_workspace(workspace_id: str, confirm_name: str, request: Request, actor: Actor, db: Db, expected: Expected):
    return response(request, delete_workspace(db, actor, workspace_id, confirm_name, expected))


@router.get("/{workspace_id}/invites")
def get_invites(workspace_id: str, request: Request, actor: Actor, db: Db):
    return response(request, list_workspace_invites(db, actor, workspace_id))


@router.post("/{workspace_id}/invites", status_code=201)
def new_invite(workspace_id: str, payload: WorkspaceInviteInput, request: Request, actor: Actor, db: Db):
    return response(request, create_workspace_invite(db, actor, workspace_id, payload))


@router.post("/{workspace_id}/invites/{invite_id}/revoke")
def revoke_invite(workspace_id: str, invite_id: str, request: Request, actor: Actor, db: Db):
    return response(request, revoke_workspace_invite(db, actor, workspace_id, invite_id))


@router.get("/{workspace_id}/join-requests")
def get_join_requests(workspace_id: str, request: Request, actor: Actor, db: Db):
    return response(request, list_join_requests(db, actor, workspace_id))


@router.post("/{workspace_id}/join-requests/{request_id}/review")
def review_join(workspace_id: str, request_id: str, payload: WorkspaceJoinReviewInput, request: Request, actor: Actor, db: Db):
    return response(request, review_join_request(db, actor, workspace_id, request_id, payload.decision))


@router.post("/{workspace_id}/members", response_model=Envelope[MemberOut])
def set_member(workspace_id: str, payload: MemberInput, request: Request, actor: Actor, db: Db):
    workspace = workspace_access(db, actor, workspace_id, "members.manage")
    user = db.get(User, payload.user_id) if payload.user_id else db.scalar(
        select(User).where(User.account == payload.account.lower()))
    if not user or not user.active:
        raise Problem(422, "VALIDATION_ERROR", "请选择启用的用户")
    if user.id == workspace.owner_id and payload.role not in {"admin", "editor"}:
        raise Problem(409, "CONFLICT", "所有者需要保留编辑或管理员角色")
    member = db.get(Membership, (workspace_id, user.id))
    # 普通空间副管理员不能修改所有者或升降级其他空间管理员
    if not actor.is_admin and actor.id != workspace.owner_id:
        if user.id == workspace.owner_id or (member and member.role == "admin") or payload.role == "admin":
            raise Problem(403, "FORBIDDEN", "只有空间所有者或系统管理员可以管理空间管理员角色")
    if member:
        member.role = payload.role
        if "quota" in payload.model_fields_set:
            member.quota = payload.quota or None
    else:
        member = Membership(workspace_id=workspace_id, user_id=user.id, role=payload.role, quota=payload.quota or None)
        db.add(member)
    audit(db, actor, "members.update", user.id, workspace_id)
    commit(db)
    return response(request, serialize(member))


@router.post("/{workspace_id}/transfer-owner", response_model=Envelope[WorkspaceOut])
def transfer_owner(workspace_id: str, payload: WorkspaceOwnerTransfer, request: Request, actor: Actor, db: Db, expected: Expected):
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or (not actor.is_admin and not db.get(Membership, (workspace_id, actor.id))):
        raise Problem(404, "NOT_FOUND", "工作空间不存在")
    if not actor.is_admin and workspace.owner_id != actor.id:
        raise Problem(403, "FORBIDDEN", "只有当前空间所有者或系统管理员可转让所有权")
    target = db.get(User, payload.user_id)
    target_member = db.get(Membership, (workspace_id, payload.user_id))
    if not target or not target.active or not target_member:
        raise Problem(422, "VALIDATION_ERROR", "目标用户须为本空间已启用成员")
    old_owner_id = workspace.owner_id
    revision_update(db, workspace, {"owner_id": target.id}, expected)
    target_member.role = "admin"
    old_member = db.get(Membership, (workspace_id, old_owner_id))
    if old_member and old_member.role != "admin":
        old_member.role = "admin"
    audit(db, actor, "workspaces.transfer_owner", target.id, workspace_id)
    commit(db)
    return response(request, serialize(workspace))


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
    actions, _ = effective_policy(db, actor)
    quota = workspace_effective_quota(db, actor, workspace_id)
    if not actor.is_admin and member.role == "viewer":
        actions = {action for action in actions if not action.endswith(WRITE_SUFFIXES)}
    elif not actor.is_admin and member.role == "annotator":
        actions = {action for action in actions if action in ANNOTATOR_ACTIONS}
    if is_workspace_admin(actor, workspace, member):
        from ..models import UserGroup
        group = db.get(UserGroup, actor.group_id) if actor.group_id else None
        denied = set(actor.deny_actions) | (set(group.deny_actions) if group else set())
        if "members.manage" not in denied:
            actions.add("members.manage")
    else:
        actions.discard("members.manage")
    return response(request, {"actions": sorted(actions), "quota": quota,
                              "role": "admin" if actor.is_admin else member.role})


@router.get("/{workspace_id}/audit", response_model=PageEnvelope[AuditOut])
def list_audit(workspace_id: str, request: Request, actor: Actor, db: Db,
               page: Page = 1, page_size: PageSize = 20):
    workspace_access(db, actor, workspace_id, "audit.read")
    items, pagination = page_data(db, select(AuditEvent).where(AuditEvent.workspace_id == workspace_id), page, page_size)
    return response(request, items, pagination=pagination)
