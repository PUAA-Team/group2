import hmac
from typing import Annotated

from fastapi import Depends, Header, Query, Request, Security
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import aware, get_db, utcnow
from ..errors import Problem
from ..models import SessionToken, User
from ..security import csrf_token, digest

Db = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=100)]


session_cookie = APIKeyCookie(name="mt_session", auto_error=False)


def current_user(request: Request, db: Db,
                 raw_cookie: Annotated[str | None, Security(session_cookie)],
                 csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    raw = raw_cookie or ""
    token = db.scalar(select(SessionToken).where(SessionToken.token_digest == digest(raw))) if raw else None
    user = db.get(User, token.user_id) if token else None
    if token is None or aware(token.expires_at) <= utcnow() or user is None or not user.active:
        raise Problem(401, "UNAUTHENTICATED", "请重新登录")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not hmac.compare_digest(csrf_header or "", csrf_token(raw)):
            raise Problem(403, "CSRF_FAILED", "请求校验失败，请刷新后重试")
    request.state.session_id = token.id
    return user


Actor = Annotated[User, Depends(current_user)]


def expected_revision(if_match: Annotated[str | None, Header()] = None):
    if if_match is None:
        raise Problem(428, "PRECONDITION_REQUIRED", "此操作需要 If-Match")
    value = if_match.strip('"')
    if not value.isdigit() or int(value) < 1:
        raise Problem(400, "INVALID_REQUEST", "If-Match 格式无效")
    return int(value)


Expected = Annotated[int, Depends(expected_revision)]
