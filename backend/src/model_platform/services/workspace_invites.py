from datetime import timedelta
import secrets

from sqlalchemy import select, update

from ..administration_models import WorkspaceInvite, WorkspaceJoinRequest
from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..models import Membership, User, Workspace
from ..permissions import workspace_access
from ..security import digest
from .common import audit, commit, serialize


def create_workspace_invite(db, actor, workspace_id, payload):
    workspace_access(db, actor, workspace_id, "members.manage")
    raw = secrets.token_urlsafe(18)
    item = WorkspaceInvite(
        id=new_id("win"),
        workspace_id=workspace_id,
        code_digest=digest(raw),
        code_preview=raw[:8] + "…",
        role=payload.role,
        require_approval=payload.require_approval,
        max_uses=payload.max_uses,
        expires_at=utcnow() + timedelta(days=payload.days),
        created_by=actor.id,
    )
    db.add(item)
    audit(db, actor, "workspaces.invite.create", item.id, workspace_id)
    commit(db)
    return {**serialize(item, exclude={"code_digest"}), "code": raw}


def list_workspace_invites(db, actor, workspace_id):
    workspace_access(db, actor, workspace_id, "members.manage")
    rows = db.scalars(
        select(WorkspaceInvite)
        .where(WorkspaceInvite.workspace_id == workspace_id)
        .order_by(WorkspaceInvite.created_at.desc())
        .limit(100)
    ).all()
    return [serialize(row, exclude={"code_digest"}) for row in rows]


def revoke_workspace_invite(db, actor, workspace_id, invite_id):
    workspace_access(db, actor, workspace_id, "members.manage")
    item = db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.id == invite_id, WorkspaceInvite.workspace_id == workspace_id))
    if item is None:
        raise Problem(404, "NOT_FOUND", "空间邀请不存在")
    if item.revoked_at is None:
        item.revoked_at = utcnow()
        audit(db, actor, "workspaces.invite.revoke", item.id, workspace_id)
        commit(db)
    return serialize(item, exclude={"code_digest"})


def _consume_invite_slot(db, invite):
    stmt = update(WorkspaceInvite).where(
        WorkspaceInvite.id == invite.id,
        WorkspaceInvite.revoked_at.is_(None),
        WorkspaceInvite.expires_at > utcnow(),
    )
    if invite.max_uses is not None:
        stmt = stmt.where(WorkspaceInvite.used_count < WorkspaceInvite.max_uses)
    result = db.execute(stmt.values(used_count=WorkspaceInvite.used_count + 1).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise Problem(409, "INVITE_EXHAUSTED", "邀请已失效或达到使用上限")


def join_workspace_by_code(db, actor, code):
    invite = db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.code_digest == digest(code)))
    now = utcnow()
    if invite is None or invite.revoked_at is not None or aware(invite.expires_at) <= now:
        raise Problem(422, "INVALID_INVITATION", "空间邀请码无效、已撤销或已过期")
    if invite.max_uses is not None and invite.used_count >= invite.max_uses:
        raise Problem(409, "INVITE_EXHAUSTED", "邀请已达到使用上限")
    workspace = db.get(Workspace, invite.workspace_id)
    if workspace is None:
        raise Problem(404, "NOT_FOUND", "工作空间不存在")
    if db.get(Membership, (workspace.id, actor.id)) is not None:
        return {"status": "already_member", "workspace_id": workspace.id, "workspace_name": workspace.name}
    if not invite.require_approval:
        _consume_invite_slot(db, invite)
        db.add(Membership(workspace_id=workspace.id, user_id=actor.id, role=invite.role))
        audit(db, actor, "workspaces.join", workspace.id, workspace.id)
        commit(db)
        return {"status": "joined", "workspace_id": workspace.id, "workspace_name": workspace.name, "role": invite.role}
    existing = db.scalar(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.workspace_id == workspace.id,
        WorkspaceJoinRequest.user_id == actor.id,
        WorkspaceJoinRequest.invite_id == invite.id,
    ))
    if existing:
        if existing.status == "rejected":
            raise Problem(409, "REQUEST_REJECTED", "该加入申请已被拒绝")
        return {"status": existing.status, "request_id": existing.id, "workspace_id": workspace.id, "workspace_name": workspace.name}
    req_row = WorkspaceJoinRequest(
        id=new_id("wjr"),
        workspace_id=workspace.id,
        invite_id=invite.id,
        user_id=actor.id,
        requested_role=invite.role,
    )
    db.add(req_row)
    audit(db, actor, "workspaces.join_request", req_row.id, workspace.id)
    commit(db)
    return {"status": "pending", "request_id": req_row.id, "workspace_id": workspace.id, "workspace_name": workspace.name}


def list_join_requests(db, actor, workspace_id):
    workspace_access(db, actor, workspace_id, "members.manage")
    rows = db.execute(
        select(WorkspaceJoinRequest, User)
        .join(User, WorkspaceJoinRequest.user_id == User.id)
        .where(WorkspaceJoinRequest.workspace_id == workspace_id)
        .order_by(WorkspaceJoinRequest.created_at.desc())
        .limit(100)
    ).all()
    return [{**serialize(req_row), "account": user.account, "display_name": user.display_name} for req_row, user in rows]


def review_join_request(db, actor, workspace_id, request_id, decision):
    workspace_access(db, actor, workspace_id, "members.manage")
    req_row = db.scalar(select(WorkspaceJoinRequest).where(
        WorkspaceJoinRequest.id == request_id,
        WorkspaceJoinRequest.workspace_id == workspace_id,
    ))
    if req_row is None:
        raise Problem(404, "NOT_FOUND", "加入申请不存在")
    if req_row.status != "pending":
        raise Problem(409, "INVALID_STATE", "该申请已处理")
    if decision == "approve":
        invite = db.get(WorkspaceInvite, req_row.invite_id)
        if invite is None:
            raise Problem(404, "NOT_FOUND", "关联邀请不存在")
        if db.get(Membership, (workspace_id, req_row.user_id)) is None:
            _consume_invite_slot(db, invite)
            db.add(Membership(workspace_id=workspace_id, user_id=req_row.user_id, role=req_row.requested_role))
        req_row.status = "approved"
    else:
        req_row.status = "rejected"
    req_row.reviewed_by = actor.id
    req_row.reviewed_at = utcnow()
    audit(db, actor, f"workspaces.join_review.{req_row.status}", req_row.id, workspace_id)
    commit(db)
    return serialize(req_row)
