from datetime import timedelta
import secrets

from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, SQLAlchemyError

from ..administration_models import Invitation, WorkspaceInvite, WorkspaceJoinRequest
from ..database import aware, new_id, utcnow
from ..errors import Problem
from ..models import AuditEvent, Membership, User, Workspace
from ..permissions import workspace_access
from ..security import digest
from .common import audit, commit, serialize


# 过期邀请清理默认保留宽限期（天）：邀请过期后宽限期内仍保留，宽限期满才删除
# （26-3；25-4 原版无宽限期，过期即删）。
DEFAULT_INVITE_SWEEP_GRACE_DAYS = 7


def sweep_expired_invites(db, actor=None, now=None, grace_days=DEFAULT_INVITE_SWEEP_GRACE_DAYS):
    """清理已过期邀请（25-4，后台定期任务与管理端手动触发共用；26-3 增加宽限期）。

    只删过期超过宽限期的行：注册邀请要求未使用且未撤销，空间邀请要求未撤销；
    已使用、已撤销的邀请是注册/操作历史，保留。宽限期内（expires_at > now - grace_days）
    的过期邀请仍保留在列表里，给管理员留出核查与恢复的时间。空间邀请关联的加入申请
    一并删除（过期邀请无法再批准，且申请表 invite_id 外键指向邀请行，不删申请删不掉
    邀请；已处理申请的批准/拒绝决定仍保留在审计事件里）。有 actor 时按空间各记一条
    审计（注册邀请 invitations.sweep、空间邀请 workspaces.invite.sweep，目标即空间 id）；
    无 actor 时只返回计数，不伪造审计操作人。返回删除计数、受影响空间与本次生效的宽限期。"""
    if grace_days is None:
        grace_days = DEFAULT_INVITE_SWEEP_GRACE_DAYS
    if grace_days < 0:
        raise Problem(422, "VALIDATION_ERROR", "宽限期不能为负数")
    now = now or utcnow()
    cutoff = now - timedelta(days=grace_days)
    expired_registrations = db.scalars(select(Invitation).where(
        Invitation.expires_at <= cutoff,
        Invitation.used_at.is_(None),
        Invitation.revoked_at.is_(None),
    )).all()
    expired_workspace = db.scalars(select(WorkspaceInvite).where(
        WorkspaceInvite.expires_at <= cutoff,
        WorkspaceInvite.revoked_at.is_(None),
    )).all()
    reg_workspaces = {item.workspace_id for item in expired_registrations}
    ws_workspaces = {item.workspace_id for item in expired_workspace}
    join_requests_deleted = 0
    try:
        if expired_workspace:
            join_requests_deleted = db.execute(delete(WorkspaceJoinRequest).where(
                WorkspaceJoinRequest.invite_id.in_([item.id for item in expired_workspace]),
            ).execution_options(synchronize_session=False)).rowcount or 0
        for item in expired_registrations:
            db.delete(item)
        for item in expired_workspace:
            db.delete(item)
    except Exception as exc:
        # 28-5：删除阶段异常打上阶段标记，供 classify_sweep_failure 按阶段归类
        # （约束冲突以外的删除阶段异常不再落到通用 SWEEP_FAILED/SWEEP_DB_ERROR）；
        # Problem 原样透传，不打标记。
        if not isinstance(exc, Problem):
            try:
                exc.sweep_stage = "delete"
            except Exception:
                pass
        raise
    if actor is not None:
        for workspace_id in sorted(reg_workspaces):
            audit(db, actor, "invitations.sweep", workspace_id, workspace_id)
        for workspace_id in sorted(ws_workspaces):
            audit(db, actor, "workspaces.invite.sweep", workspace_id, workspace_id)
    if expired_registrations or expired_workspace or join_requests_deleted:
        commit(db)
    return {"registration_deleted": len(expired_registrations),
            "workspace_deleted": len(expired_workspace),
            "join_requests_deleted": join_requests_deleted,
            "workspaces": sorted(reg_workspaces | ws_workspaces),
            "grace_days": grace_days}


def classify_sweep_failure(exc):
    """把清理失败的异常归为原因码（27-4，26-3 残留；28-5 细化）：失败审计与 CLI stderr
    输出同步带上该码，替代原来一律的 SWEEP_FAILED。

    - Problem：直接沿用其业务码（如 VALIDATION_ERROR、INTERNAL_ERROR）；
    - OperationalError：按底层错误码/消息再区分——连接超时 SWEEP_DB_TIMEOUT
      （SQLSTATE 57014，或消息含 timeout/timed out）、连接被拒/连不上
      SWEEP_DB_CONN_REFUSED（消息含 connection refused / could not connect /
      no route to host 等），其余仍为 SWEEP_DB_UNAVAILABLE；
    - IntegrityError：约束冲突（通常是删除单行时外键/唯一约束失败），SWEEP_DELETE_FAILED；
    - 删除阶段异常（sweep_expired_invites 在删除阶段打上的 sweep_stage="delete" 标记）：
      约束冲突以外的异常也归为 SWEEP_DELETE_FAILED，不再落到通用码；
    - 其余 DBAPIError/SQLAlchemyError：数据库层其他错误，SWEEP_DB_ERROR；
    - 其他异常：SWEEP_FAILED（兜底，与 26-3 旧码一致）。"""
    if isinstance(exc, Problem):
        return exc.code
    if isinstance(exc, OperationalError):
        return _classify_operational_error(exc)
    if isinstance(exc, IntegrityError):
        return "SWEEP_DELETE_FAILED"
    if getattr(exc, "sweep_stage", None) == "delete":
        return "SWEEP_DELETE_FAILED"
    if isinstance(exc, (DBAPIError, SQLAlchemyError)):
        return "SWEEP_DB_ERROR"
    return "SWEEP_FAILED"


# psycopg3（生产驱动）用 sqlstate，psycopg2 用 pgcode；SQLite 等驱动无错误码，
# 只看消息。57014 为查询取消/语句超时。
_TIMEOUT_SQLSTATES = {"57014"}
_TIMEOUT_KEYWORDS = ("timed out", "timeout")
# 连接被拒/不可达：libpq/psycopg 的拒绝消息里含 "Connection refused"，
# 鉴权失败（FATAL: password authentication failed）不含这些词，不会误判。
_CONN_REFUSED_KEYWORDS = (
    "connection refused", "could not connect", "no route to host",
    "network is unreachable", "name or service not known",
    "temporary failure in name resolution", "connection reset",
    "connection aborted", "server closed the connection",
    "no such host", "nodename nor servname",
)


def _classify_operational_error(exc):
    """OperationalError 再细分（28-5）：先看底层错误码，再看异常与底层异常的消息关键字。"""
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate in _TIMEOUT_SQLSTATES:
        return "SWEEP_DB_TIMEOUT"
    text = " ".join(part for part in (str(exc), str(orig) if orig is not None else "") if part).lower()
    if any(keyword in text for keyword in _TIMEOUT_KEYWORDS):
        return "SWEEP_DB_TIMEOUT"
    if any(keyword in text for keyword in _CONN_REFUSED_KEYWORDS):
        return "SWEEP_DB_CONN_REFUSED"
    return "SWEEP_DB_UNAVAILABLE"


def record_sweep_failure(db, actor, error_code="SWEEP_FAILED"):
    """定时清理失败时记一条失败审计（26-3）：操作人为触发清理的管理员，目标固定为
    sweep（清理无归属空间），result=failure；无操作人不伪造审计。调用方在独立会话里
    调用（失败事务已回滚），本函数只负责写审计行，不掩盖原错。27-4：error_code
    由调用方按 classify_sweep_failure(exc) 归类后传入，默认 SWEEP_FAILED 兜底。"""
    if actor is None:
        return
    db.add(AuditEvent(id=new_id("evt"), actor_id=actor.id, workspace_id=None,
                      action="invitations.sweep_failed", target_id="sweep",
                      result="failure", error_code=error_code))
    commit(db)


def invite_expiry_state(expires_at, now=None, grace_days=DEFAULT_INVITE_SWEEP_GRACE_DAYS):
    """邀请过期后的宽限期状态（27-3，26-3 残留）：未过期返回 None；过期未满
    宽限期返回 "expired_grace"（仍保留待清理）；过期超过宽限期返回 "expired"
    （下次清理会删除）。与 sweep_expired_invites 的宽限期口径一致。"""
    now = now or utcnow()
    if grace_days is None:
        grace_days = DEFAULT_INVITE_SWEEP_GRACE_DAYS
    expires = aware(expires_at)
    if expires > now:
        return None
    if expires > now - timedelta(days=grace_days):
        return "expired_grace"
    return "expired"


def invite_status(invite, now=None, grace_days=DEFAULT_INVITE_SWEEP_GRACE_DAYS):
    """空间邀请的展示状态：revoked（已撤销）/ expired_grace（已过期，宽限期内）/
    expired（已过期，已过宽限期）/ exhausted（已用完）/ active（有效）。"""
    now = now or utcnow()
    if invite.revoked_at is not None:
        return "revoked"
    expired = invite_expiry_state(invite.expires_at, now, grace_days)
    if expired is not None:
        return expired
    if invite.max_uses is not None and invite.used_count >= invite.max_uses:
        return "exhausted"
    return "active"


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


def list_workspace_invites(db, actor, workspace_id, grace_days=DEFAULT_INVITE_SWEEP_GRACE_DAYS):
    # 28-2：列表展示宽限期与清理口径对齐，显式 grace_days 透传给 invite_status
    # （0–365，默认 7 天，与手动清理接口同一校验与默认值）。
    workspace_access(db, actor, workspace_id, "members.manage")
    rows = db.scalars(
        select(WorkspaceInvite)
        .where(WorkspaceInvite.workspace_id == workspace_id)
        .order_by(WorkspaceInvite.created_at.desc())
        .limit(100)
    ).all()
    now = utcnow()
    return [{**serialize(row, exclude={"code_digest"}), "status": invite_status(row, now, grace_days)} for row in rows]


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
        # 批准前先明确关联邀请是否仍有效：已撤销/已过期/已用完都不能再批准，
        # 申请保持 pending，管理员可拒绝该申请或重新签发邀请。
        status = invite_status(invite)
        if status == "revoked":
            raise Problem(409, "INVITE_REVOKED", "关联邀请已被撤销，无法批准")
        if status in ("expired", "expired_grace"):
            raise Problem(409, "INVITE_EXPIRED", "关联邀请已过期，无法批准")
        if status == "exhausted":
            raise Problem(409, "INVITE_EXHAUSTED", "关联邀请已达到使用上限，无法批准")
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
