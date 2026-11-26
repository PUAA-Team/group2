import secrets
from datetime import timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete, select, update

from ..database import aware, new_id, utcnow
from ..errors import Problem, response
from ..models import LoginAttempt, PasswordResetCode, SessionToken, User
from ..outputs import Envelope, SessionOut
from ..permissions import require_admin
from ..schemas import Login, PasswordReset, PasswordResetCodeIssue
from ..security import digest, hash_password, hmac_digest, verify_password
from ..services.common import audit, commit
from ..services.identity import session_data
from .deps import Actor, Db

router = APIRouter(prefix="/api/v1/auth", tags=["身份认证"])
# 未知用户也执行同等成本的密码验证。
DUMMY_PASSWORD = hash_password(secrets.token_urlsafe(24))
# 重置码字符表：去掉易混淆的 0/O、1/I/L，用户手抄不易错。
_RESET_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_reset_code():
    return "".join(secrets.choice(_RESET_CODE_ALPHABET) for _ in range(8))


def _reset_code_digest(code, secret):
    return hmac_digest(f"password-reset:{code}", secret)


def _is_blocked(attempt, now):
    return attempt is not None and attempt.blocked_until is not None and aware(attempt.blocked_until) > now


def _reset_if_unblocked(attempt, now):
    # 锁定期已过：计数归零，滑动窗口重新起计。
    if attempt is not None and attempt.blocked_until is not None and aware(attempt.blocked_until) <= now:
        attempt.failures = 0
        attempt.blocked_until = None
        attempt.window_started_at = None


def _record_failure(db, key, now, threshold, lock_seconds, window_seconds=None):
    """累计一次失败并在达到阈值时锁定；返回更新后的记录。

    window_seconds 为 None 时按固定计数桶处理（单 IP 桶沿用旧语义）；
    否则按滑动窗口处理：窗口过期则计数归零重新起计。
    """
    attempt = db.get(LoginAttempt, key)
    if attempt is None:
        attempt = LoginAttempt(key_digest=key, failures=0, window_started_at=now if window_seconds else None)
        db.add(attempt)
    _reset_if_unblocked(attempt, now)
    if window_seconds is not None:
        started = aware(attempt.window_started_at) if attempt.window_started_at else None
        if started is None or (now - started).total_seconds() >= window_seconds:
            attempt.failures = 0
            attempt.window_started_at = now
    attempt.failures += 1
    if attempt.failures >= threshold:
        attempt.blocked_until = now + timedelta(seconds=lock_seconds)
    return attempt


@router.post("/login", response_model=Envelope[SessionOut])
def login(payload: Login, request: Request, output: Response, db: Db):
    settings = request.app.state.settings
    account = payload.account.strip().lower()
    client = request.client.host if request.client else "unknown"
    # 单 IP 桶：沿用旧语义；账号桶：纯账号维度全局滑动计数，轮换 IP 也无法绕过。
    ip_key = digest(f"{account}|{client}")
    account_key = digest(f"account|{account}")
    ip_attempt = db.get(LoginAttempt, ip_key)
    account_attempt = db.get(LoginAttempt, account_key)
    now = utcnow()
    if _is_blocked(ip_attempt, now) or _is_blocked(account_attempt, now):
        raise Problem(429, "RATE_LIMITED", "登录尝试过多，请稍后重试")
    user = db.scalar(select(User).where(User.account == account))
    password_valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD)
    if not user or not user.active or not password_valid:
        _record_failure(db, ip_key, now, settings.login_failures, settings.login_lock_seconds)
        _record_failure(db, account_key, now, settings.login_account_failures,
                        settings.login_account_lock_seconds, settings.login_account_window_seconds)
        commit(db)
        raise Problem(401, "INVALID_CREDENTIALS", "账号或密码错误")
    if ip_attempt:
        db.delete(ip_attempt)
    if account_attempt:
        db.delete(account_attempt)
    raw = secrets.token_urlsafe(48)
    token = SessionToken(id=new_id("ses"), user_id=user.id, token_digest=digest(raw),
                         expires_at=now + timedelta(hours=settings.session_hours))
    db.add(token)
    audit(db, user, "auth.login", user.id)
    commit(db)
    output.set_cookie("mt_session", raw, httponly=True, secure=settings.secure_cookie,
                      samesite="strict", max_age=settings.session_hours * 3600, path="/")
    return response(request, session_data(db, user, raw, settings.resolved_csrf_secret))


@router.post("/password-reset-codes", status_code=201)
def issue_password_reset_code(payload: PasswordResetCodeIssue, request: Request, actor: Actor, db: Db):
    """管理员签发一次性密码重置码（Stage 20A-1）。

    明文码只在本次响应里返回一次，库里只存 HMAC-SHA-256 摘要；
    签发新码时作废该用户此前未使用的旧码，同一时间只有一个有效码。
    """
    require_admin(db, actor, "users.manage")
    account = payload.account.strip().lower()
    user = db.scalar(select(User).where(User.account == account))
    if user is None:
        raise Problem(404, "NOT_FOUND", "用户不存在")
    now = utcnow()
    settings = request.app.state.settings
    db.execute(delete(PasswordResetCode).where(
        PasswordResetCode.user_id == user.id, PasswordResetCode.used_at.is_(None)))
    raw = _new_reset_code()
    item = PasswordResetCode(
        id=new_id("prc"), user_id=user.id,
        code_digest=_reset_code_digest(raw, settings.resolved_csrf_secret),
        expires_at=now + timedelta(minutes=settings.password_reset_code_minutes),
        created_by=actor.id)
    db.add(item)
    audit(db, actor, "auth.password.reset_code.issue", user.id)
    commit(db)
    return response(request, {"user_id": user.id, "account": user.account, "code": raw,
                             "expires_at": aware(item.expires_at).isoformat()})


@router.post("/password-reset")
def reset_password_by_code(payload: PasswordReset, request: Request, db: Db):
    """用户凭重置码自助重置密码（Stage 20A-1）。

    码 15 分钟过期、一次有效；重置成功后改密码、踢出该用户全部历史
    会话并清除登录限流计数。未知账号与错误/过期码返回同一错误，
    不泄露账号是否存在；猜码失败计入账号桶，暴力猜码会触发账号锁定，
    但已锁定的账号仍可凭有效码重置（重置即是锁定的恢复路径）。
    """
    settings = request.app.state.settings
    account = payload.account.strip().lower()
    now = utcnow()
    user = db.scalar(select(User).where(User.account == account))
    row = None
    if user is not None:
        row = db.scalar(select(PasswordResetCode).where(
            PasswordResetCode.user_id == user.id,
            PasswordResetCode.code_digest == _reset_code_digest(payload.code, settings.resolved_csrf_secret),
            PasswordResetCode.used_at.is_(None),
            PasswordResetCode.expires_at > now))
    if user is None or not user.active or row is None:
        _record_failure(db, digest(f"account|{account}"), now, settings.login_account_failures,
                        settings.login_account_lock_seconds, settings.login_account_window_seconds)
        commit(db)
        raise Problem(400, "INVALID_RESET_CODE", "重置码无效或已过期")
    db.execute(update(User).where(User.id == user.id).values(
        password_hash=hash_password(payload.password),
        revision=User.revision + 1).execution_options(synchronize_session=False))
    row.used_at = now
    db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    client = request.client.host if request.client else "unknown"
    for key in (digest(f"account|{account}"), digest(f"{account}|{client}")):
        attempt = db.get(LoginAttempt, key)
        if attempt is not None:
            db.delete(attempt)
    audit(db, user, "auth.password.reset_by_code", user.id)
    commit(db)
    return response(request, {"reset": True})


@router.get("/session", response_model=Envelope[SessionOut])
def session(request: Request, actor: Actor, db: Db):
    return response(request, session_data(db, actor, request.cookies["mt_session"], request.app.state.settings.resolved_csrf_secret))


@router.post("/logout", response_model=Envelope[dict[str, bool]])
def logout(request: Request, output: Response, actor: Actor, db: Db):
    db.execute(delete(SessionToken).where(SessionToken.id == request.state.session_id))
    audit(db, actor, "auth.logout", actor.id)
    commit(db)
    output.delete_cookie("mt_session", path="/", secure=request.app.state.settings.secure_cookie,
                         httponly=True, samesite="strict")
    return response(request, {"logged_out": True})


@router.get("/sessions")
def list_sessions(request: Request, actor: Actor, db: Db):
    now = utcnow()
    rows = db.scalars(
        select(SessionToken)
        .where(SessionToken.user_id == actor.id, SessionToken.expires_at > now)
        .order_by(SessionToken.created_at.desc(), SessionToken.id.desc())
    ).all()
    current_id = request.state.session_id
    return response(request, [
        {
            "id": row.id,
            "created_at": aware(row.created_at).isoformat(),
            "expires_at": aware(row.expires_at).isoformat(),
            "current": row.id == current_id,
        }
        for row in rows
    ])


@router.post("/sessions/revoke-others")
def revoke_other_sessions(request: Request, actor: Actor, db: Db):
    res = db.execute(
        delete(SessionToken).where(SessionToken.user_id == actor.id, SessionToken.id != request.state.session_id)
    )
    audit(db, actor, "auth.sessions.revoke_others", actor.id)
    commit(db)
    return response(request, {"revoked": int(res.rowcount or 0)})


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: str, request: Request, output: Response, actor: Actor, db: Db):
    row = db.scalar(select(SessionToken).where(SessionToken.id == session_id, SessionToken.user_id == actor.id))
    if row is None:
        raise Problem(404, "NOT_FOUND", "会话不存在")
    is_current = row.id == request.state.session_id
    db.delete(row)
    audit(db, actor, "auth.session.revoke", session_id)
    commit(db)
    if is_current:
        output.delete_cookie("mt_session", path="/", secure=request.app.state.settings.secure_cookie,
                             httponly=True, samesite="strict")
    return response(request, {"revoked": True, "current": is_current})
