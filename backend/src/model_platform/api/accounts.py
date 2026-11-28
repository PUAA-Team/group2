from datetime import timedelta
import secrets
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import delete, select, update

from ..administration_models import Invitation
from ..administration_schemas import InviteInput, PasswordInput, ProfileInput, RegisterInput
from ..database import aware, new_id, utcnow
from ..errors import Problem, response
from ..models import Membership, SessionToken, User, UserGroup, Workspace
from ..permissions import effective_policy, require_admin, workspace_access
from ..security import digest, hash_password, verify_password
from ..schemas import WorkspaceCreate
from ..services.common import audit, commit, revision_update, serialize
from ..services.platform_settings import platform_config
from ..services.workspace_invites import (
    DEFAULT_INVITE_SWEEP_GRACE_DAYS, classify_sweep_failure, invite_expiry_state,
    sweep_expired_invites)
from .deps import Actor, Db, Expected

router = APIRouter(prefix="/api/v1", tags=["账号与协作"])


@router.patch("/auth/profile")
def profile(payload: ProfileInput, request: Request, actor: Actor, db: Db, expected: Expected):
    revision_update(db, actor, payload.model_dump(), expected)
    audit(db, actor, "users.profile", actor.id); commit(db)
    return response(request, serialize(actor))


def change_password(db, actor, user, payload):
    if not payload.password.strip():
        raise Problem(422, "VALIDATION_ERROR", "密码不能为空")
    db.execute(update(User).where(User.id == user.id).values(password_hash=hash_password(payload.password), revision=User.revision + 1).execution_options(synchronize_session=False))
    db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    audit(db, actor, "users.password", user.id); commit(db)


@router.post("/auth/password")
def own_password(payload: PasswordInput, request: Request, output: Response, actor: Actor, db: Db):
    if not payload.current_password or not verify_password(payload.current_password, actor.password_hash):
        raise Problem(403, "INVALID_PASSWORD", "原密码不正确")
    change_password(db, actor, actor, payload)
    output.delete_cookie("mt_session", path="/", secure=request.app.state.settings.secure_cookie, httponly=True, samesite="strict")
    return response(request, {"changed": True, "login_required": True})


@router.post("/admin/users/{user_id}/password")
def reset_password(user_id: str, payload: PasswordInput, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "users.manage")
    user = db.get(User, user_id)
    if user is None:
        raise Problem(404, "NOT_FOUND", "用户不存在")
    change_password(db, actor, user, payload)
    return response(request, {"changed": True})


@router.get("/admin/users/{user_id}/access")
def user_access(user_id: str, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "users.manage")
    user = db.get(User, user_id)
    if user is None:
        raise Problem(404, "NOT_FOUND", "用户不存在")
    actions, quota = effective_policy(db, user)
    memberships = [serialize(item) for item in db.scalars(select(Membership).where(Membership.user_id == user_id))]
    return response(request, {"actions": sorted(actions), "quota": quota, "memberships": memberships})


@router.get("/admin/invitations")
def list_invitations(request: Request, actor: Actor, db: Db,
                     grace_days: Annotated[int, Query(ge=0, le=365)] = DEFAULT_INVITE_SWEEP_GRACE_DAYS):
    require_admin(db, actor, "users.manage")
    rows = db.execute(
        select(Invitation, Workspace, User)
        .join(Workspace, Invitation.workspace_id == Workspace.id)
        .outerjoin(User, Invitation.used_by == User.id)
        .order_by(Invitation.created_at.desc())
        .limit(100)
    ).all()
    now = utcnow()
    result = []
    for item, workspace, used_by in rows:
        if item.revoked_at is not None:
            status = "revoked"
        elif item.used_at is not None:
            status = "used"
        else:
            # 已过期按宽限期区分展示（27-3）：宽限期内 expired_grace、已过宽限期 expired。
            # 28-2：宽限期由查询参数传入（0–365，默认 7 天），与手动清理接口
            # 同一校验与默认值，展示与清理口径对齐。
            status = invite_expiry_state(item.expires_at, now, grace_days) or "active"
        result.append({**serialize(item, exclude={"token_digest"}), "status": status,
                       "workspace_name": workspace.name, "used_by_account": used_by.account if used_by else None})
    # 29-1（28-2 残留）：响应顶层回显当前生效的宽限期天数（默认 7 天，
    # 显式传参时回显传入值），供前端选择器按接口返回回显，不再只按 URL 参数回显。
    return response(request, result, extra={"grace_days": grace_days})


@router.post("/admin/invitations/sweep")
def sweep_invitations(request: Request, actor: Actor, db: Db,
                      grace_days: Annotated[int, Query(ge=0, le=365)] = DEFAULT_INVITE_SWEEP_GRACE_DAYS):
    # 阶段 25-4：手动触发过期邀请清理，与定时任务共用同一服务函数；
    # 触发管理员作为审计操作人记账。26-3：grace_days 透传，默认 7 天宽限期。
    # 27-4：非 Problem 异常按失败原因归类后转 Problem(500, 原因码) 抛出，
    # 通用失败审计机制只记一条 invitations.sweep_failed，error_code 即原因码
    # （Problem 原样透传，沿用其业务码，如 26-3 测试的 INTERNAL_ERROR）。
    require_admin(db, actor, "users.manage")
    try:
        return response(request, sweep_expired_invites(db, actor, grace_days=grace_days))
    except Problem:
        raise
    except Exception as exc:
        raise Problem(500, classify_sweep_failure(exc), "邀请清理失败") from exc


@router.post("/admin/invitations/{invitation_id}/revoke")
def revoke_invitation(invitation_id: str, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "users.manage")
    item = db.get(Invitation, invitation_id)
    if item is None:
        raise Problem(404, "NOT_FOUND", "注册邀请不存在")
    if item.revoked_at is None:
        item.revoked_at = utcnow()
        audit(db, actor, "invitations.revoke", item.id, item.workspace_id)
        commit(db)
    return response(request, serialize(item, exclude={"token_digest"}))


@router.post("/admin/invitations", status_code=201)
def invite(payload: InviteInput, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "users.manage")
    if not platform_config(db).invitations_enabled:
        raise Problem(409, "INVITATIONS_DISABLED", "邀请注册已关闭")
    workspace_access(db, actor, payload.workspace_id, "members.manage")
    if payload.group_id and not db.get(UserGroup, payload.group_id):
        raise Problem(422, "VALIDATION_ERROR", "用户组不存在")
    raw = secrets.token_urlsafe(32)
    item = Invitation(id=new_id("inv"), token_digest=digest(raw), workspace_id=payload.workspace_id, group_id=payload.group_id,
                      role=payload.role, expires_at=utcnow() + timedelta(days=payload.days), created_by=actor.id)
    db.add(item); audit(db, actor, "invitations.create", item.id, payload.workspace_id); commit(db)
    return response(request, {**serialize(item), "invitation": raw})


@router.post("/auth/register", status_code=201)
def register(payload: RegisterInput, request: Request, db: Db):
    config = platform_config(db)
    user_payload = payload.user_payload()
    if payload.invitation:
        if not config.invitations_enabled:
            raise Problem(409, "INVITATIONS_DISABLED", "邀请注册已关闭")
        item = db.scalar(select(Invitation).where(Invitation.token_digest == digest(payload.invitation)))
        now = utcnow()
        if item is None or item.used_at or item.revoked_at or aware(item.expires_at) <= now:
            raise Problem(422, "INVALID_INVITATION", "邀请码无效、已使用、已撤销或已到期")
        result = db.execute(update(Invitation).where(Invitation.id == item.id, Invitation.used_at.is_(None), Invitation.revoked_at.is_(None), Invitation.expires_at > now).values(used_at=now).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise Problem(409, "INVALID_INVITATION", "邀请码已使用")
        user = User(id=new_id("usr"), account=user_payload.account, display_name=user_payload.display_name, password_hash=hash_password(user_payload.password), group_id=item.group_id)
        db.add(user); db.flush()
        db.add(Membership(workspace_id=item.workspace_id, user_id=user.id, role=item.role))
        db.execute(update(Invitation).where(Invitation.id == item.id).values(used_by=user.id))
        audit(db, user, "auth.register", user.id, item.workspace_id); commit(db)
        return response(request, {"registered": True, "account": user.account})
    if not config.self_registration_enabled:
        raise Problem(409, "REGISTRATION_DISABLED", "开放注册未开启，请使用邀请码或联系管理员")
    group_id = config.default_group_id if config.default_group_id and db.get(UserGroup, config.default_group_id) else None
    user = User(id=new_id("usr"), account=user_payload.account, display_name=user_payload.display_name,
                password_hash=hash_password(user_payload.password), group_id=group_id)
    db.add(user); db.flush()
    audit(db, user, "auth.register.self", user.id); commit(db)
    return response(request, {"registered": True, "account": user.account})


@router.patch("/workspaces/{workspace_id}")
def rename_workspace(workspace_id: str, payload: WorkspaceCreate, request: Request, actor: Actor, db: Db, expected: Expected):
    space = workspace_access(db, actor, workspace_id, "members.manage")
    revision_update(db, space, {"name": payload.name}, expected)
    audit(db, actor, "workspaces.update", space.id, space.id); commit(db)
    return response(request, serialize(space))


@router.post("/workspaces/{workspace_id}/members/{user_id}/remove")
def remove_member(workspace_id: str, user_id: str, request: Request, actor: Actor, db: Db):
    space = workspace_access(db, actor, workspace_id, "members.manage")
    if user_id == space.owner_id:
        raise Problem(409, "OWNER_PROTECTED", "空间所有者需要保留成员身份")
    member = db.get(Membership, (workspace_id, user_id))
    if member is None:
        raise Problem(404, "NOT_FOUND", "成员不存在")
    db.delete(member); audit(db, actor, "members.remove", user_id, workspace_id); commit(db)
    return response(request, {"removed": True})
