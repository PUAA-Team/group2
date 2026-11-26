"""Stage 20A-1：管理员签发一次性密码重置码，用户自助重置密码。"""
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from model_platform.database import utcnow
from model_platform.models import LoginAttempt, PasswordResetCode
from model_platform.security import digest
from conftest import PASSWORD, create_user, login

ACCOUNT = "member"
NEW_PASSWORD = "reset-new-password-2026"
ACCOUNT_KEY = digest(f"account|{ACCOUNT}")


def _issue(admin, account=ACCOUNT):
    result = admin.post("/api/v1/auth/password-reset-codes", json={"account": account})
    assert result.status_code == 201, result.text
    return result.json()["data"]


def _reset(client, code, account=ACCOUNT, password=NEW_PASSWORD):
    return client.post("/api/v1/auth/password-reset",
                       json={"account": account, "code": code, "password": password})


def test_issue_requires_admin_and_known_user(app, admin):
    create_user(admin, account=ACCOUNT)
    with TestClient(app) as member:
        login(member, ACCOUNT)
        assert member.post("/api/v1/auth/password-reset-codes",
                           json={"account": ACCOUNT}).status_code == 403
    assert admin.post("/api/v1/auth/password-reset-codes",
                      json={"account": "ghost"}).status_code == 404
    data = _issue(admin)
    assert len(data["code"]) == 8 and data["account"] == ACCOUNT
    assert data["expires_at"]
    # 库里只存摘要，不存明文码。
    with app.state.sessions() as db:
        row = db.scalar(select(PasswordResetCode))
        assert row is not None and row.code_digest != data["code"]
        assert len(row.code_digest) == 64 and row.used_at is None


def test_reset_revokes_sessions_and_old_password_fails(app, admin):
    user = create_user(admin, account=ACCOUNT)
    data = _issue(admin)
    with TestClient(app) as member:
        login(member, ACCOUNT)
        assert member.get("/api/v1/auth/session").status_code == 200
        assert _reset(member, data["code"]).status_code == 200
        # 重置后旧会话被踢出、旧密码失效、新密码可登录。
        assert member.get("/api/v1/auth/session").status_code == 401
        assert member.post("/api/v1/auth/login",
                           json={"account": ACCOUNT, "password": PASSWORD}).status_code == 401
        result = member.post("/api/v1/auth/login",
                             json={"account": ACCOUNT, "password": NEW_PASSWORD})
        assert result.status_code == 200, result.text
    with app.state.sessions() as db:
        row = db.scalar(select(PasswordResetCode).where(PasswordResetCode.user_id == user["id"]))
        assert row is not None and row.used_at is not None


def test_code_is_single_use(app, admin):
    create_user(admin, account=ACCOUNT)
    data = _issue(admin)
    with TestClient(app) as client:
        assert _reset(client, data["code"]).status_code == 200
        assert _reset(client, data["code"]).status_code == 400
        assert _reset(client, data["code"]).json()["error"]["code"] == "INVALID_RESET_CODE"


def test_expired_code_rejected(app, admin):
    create_user(admin, account=ACCOUNT)
    data = _issue(admin)
    with app.state.sessions() as db:
        row = db.scalar(select(PasswordResetCode))
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    with TestClient(app) as client:
        assert _reset(client, data["code"]).status_code == 400


def test_new_code_invalidates_previous(app, admin):
    create_user(admin, account=ACCOUNT)
    old = _issue(admin)
    new = _issue(admin)
    assert old["code"] != new["code"]
    with TestClient(app) as client:
        assert _reset(client, old["code"]).status_code == 400
        assert _reset(client, new["code"]).status_code == 200


def test_wrong_code_rejected_and_unknown_account_same_error(app, admin):
    create_user(admin, account=ACCOUNT)
    data = _issue(admin)
    with TestClient(app) as client:
        assert _reset(client, "AAAAAAAA").status_code == 400
        assert _reset(client, "AAAAAAAA").json()["error"]["code"] == "INVALID_RESET_CODE"
        # 未知账号返回同一错误，不泄露账号是否存在；正确码仍可用。
        assert _reset(client, data["code"], account="ghost").status_code == 400
        assert _reset(client, data["code"]).status_code == 200


def test_repeated_wrong_codes_lock_account(app, admin):
    create_user(admin, account=ACCOUNT)
    with TestClient(app) as client:
        for _ in range(15):
            assert _reset(client, "AAAAAAAA").status_code == 400
        # 暴力猜码 15 次后账号被锁定，登录也被拒绝。
        assert client.post("/api/v1/auth/login",
                           json={"account": ACCOUNT, "password": PASSWORD}).status_code == 429
        row = None
        with app.state.sessions() as db:
            row = db.get(LoginAttempt, ACCOUNT_KEY)
        assert row is not None and row.failures == 15


def test_reset_clears_account_lock(app, admin):
    create_user(admin, account=ACCOUNT)
    data = _issue(admin)
    with TestClient(app) as client:
        for _ in range(15):
            assert _reset(client, "AAAAAAAA").status_code == 400
        assert client.post("/api/v1/auth/login",
                           json={"account": ACCOUNT, "password": PASSWORD}).status_code == 429
        # 已锁定的账号仍可凭有效码重置，重置后锁定清除、新密码可登录。
        assert _reset(client, data["code"]).status_code == 200
        with app.state.sessions() as db:
            assert db.get(LoginAttempt, ACCOUNT_KEY) is None
        assert client.post("/api/v1/auth/login",
                           json={"account": ACCOUNT, "password": NEW_PASSWORD}).status_code == 200
