import secrets
from datetime import timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete, select

from ..database import aware, new_id, utcnow
from ..errors import Problem, response
from ..models import LoginAttempt, SessionToken, User
from ..outputs import Envelope, SessionOut
from ..schemas import Login
from ..security import digest, hash_password, verify_password
from ..services.common import audit, commit
from ..services.identity import session_data
from .deps import Actor, Db

router = APIRouter(prefix="/api/v1/auth", tags=["身份认证"])
# 未知用户也执行同等成本的密码验证。
DUMMY_PASSWORD = hash_password(secrets.token_urlsafe(24))


@router.post("/login", response_model=Envelope[SessionOut])
def login(payload: Login, request: Request, output: Response, db: Db):
    settings = request.app.state.settings
    account = payload.account.strip().lower()
    client = request.client.host if request.client else "unknown"
    key = digest(f"{account}|{client}")
    attempt = db.get(LoginAttempt, key)
    now = utcnow()
    if attempt and attempt.blocked_until and aware(attempt.blocked_until) > now:
        raise Problem(429, "RATE_LIMITED", "登录尝试过多，请稍后重试")
    if attempt and attempt.blocked_until:
        attempt.failures = 0
        attempt.blocked_until = None
    user = db.scalar(select(User).where(User.account == account))
    password_valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD)
    if not user or not user.active or not password_valid:
        if attempt is None:
            attempt = LoginAttempt(key_digest=key, failures=0)
            db.add(attempt)
        attempt.failures += 1
        if attempt.failures >= settings.login_failures:
            attempt.blocked_until = now + timedelta(seconds=settings.login_lock_seconds)
        commit(db)
        raise Problem(401, "INVALID_CREDENTIALS", "账号或密码错误")
    if attempt:
        db.delete(attempt)
    raw = secrets.token_urlsafe(48)
    token = SessionToken(id=new_id("ses"), user_id=user.id, token_digest=digest(raw),
                         expires_at=now + timedelta(hours=settings.session_hours))
    db.add(token)
    audit(db, user, "auth.login", user.id)
    commit(db)
    output.set_cookie("mt_session", raw, httponly=True, secure=settings.secure_cookie,
                      samesite="strict", max_age=settings.session_hours * 3600, path="/")
    return response(request, session_data(db, user, raw))


@router.get("/session", response_model=Envelope[SessionOut])
def session(request: Request, actor: Actor, db: Db):
    return response(request, session_data(db, actor, request.cookies["mt_session"]))


@router.post("/logout", response_model=Envelope[dict[str, bool]])
def logout(request: Request, output: Response, actor: Actor, db: Db):
    db.execute(delete(SessionToken).where(SessionToken.id == request.state.session_id))
    audit(db, actor, "auth.logout", actor.id)
    commit(db)
    output.delete_cookie("mt_session", path="/", secure=request.app.state.settings.secure_cookie,
                         httponly=True, samesite="strict")
    return response(request, {"logged_out": True})
