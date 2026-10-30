from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from model_platform.database import utcnow
from model_platform.models import SessionToken, User
from model_platform.security import verify_password
from conftest import PASSWORD, create_user, login


def test_login_cookie_secret_and_logout(app):
    with TestClient(app) as client:
        result = login(client)
        cookie = result.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert "password_hash" not in result.text and "token_digest" not in result.text
        with app.state.sessions() as db:
            user = db.scalar(select(User).where(User.account == "owner"))
            token = db.scalar(select(SessionToken))
            assert PASSWORD not in user.password_hash
            assert verify_password(PASSWORD, user.password_hash)
            assert token.token_digest != client.cookies["mt_session"]
        assert client.get("/api/v1/auth/session").json()["data"]["csrf_token"] == client.headers["X-CSRF-Token"]
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/session").status_code == 401


def test_csrf_and_origin(app, admin):
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/v1/admin/users").status_code == 401
        result = anonymous.post("/api/v1/auth/login", json={"account": "owner", "password": PASSWORD},
                                headers={"Origin": "https://evil.example"})
        assert result.status_code == 403
    token = admin.headers.pop("X-CSRF-Token")
    assert admin.post("/api/v1/workspaces", json={"name": "x"}).status_code == 403
    admin.headers["X-CSRF-Token"] = "wrong"
    assert admin.post("/api/v1/workspaces", json={"name": "x"}).status_code == 403
    admin.headers["X-CSRF-Token"] = token
    allowed = admin.post("/api/v1/workspaces", json={"name": "x"}, headers={"Origin": "http://127.0.0.1:8765"})
    assert allowed.status_code == 201
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:8765"


@pytest.mark.parametrize("account", ["owner", "unknown"])
def test_wrong_password_and_lock(app, account):
    with TestClient(app) as client:
        for _ in range(5):
            result = client.post("/api/v1/auth/login", json={"account": account, "password": "wrong"})
            assert result.status_code == 401
            assert result.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert client.post("/api/v1/auth/login", json={"account": account, "password": PASSWORD}).status_code == 429


def test_expiration(app, admin):
    with app.state.sessions() as db:
        token = db.scalar(select(SessionToken))
        token.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert admin.get("/api/v1/auth/session").status_code == 401


def test_disabled_user_session_cannot_revive(app, admin):
    user = create_user(admin)
    with TestClient(app) as client:
        login(client, "member")
        result = admin.patch(f"/api/v1/admin/users/{user['id']}", json={"active": False}, headers={"If-Match": '"1"'})
        assert result.status_code == 200
        assert client.get("/api/v1/auth/session").status_code == 401
        assert admin.patch(f"/api/v1/admin/users/{user['id']}", json={"active": True}, headers={"If-Match": '"2"'}).status_code == 200
        assert client.get("/api/v1/auth/session").status_code == 401


def test_admin_invariant_and_validation(admin):
    owner = admin.get("/api/v1/auth/session").json()["data"]["user"]
    assert admin.patch(f"/api/v1/admin/users/{owner['id']}", json={"active": False}, headers={"If-Match": '"1"'}).status_code == 409
    secret = "never-echo-this-password"
    result = admin.post("/api/v1/admin/users", json={"account": "invalid space", "display_name": "x", "password": secret, "status": "admin"})
    assert result.status_code == 422 and secret not in result.text
    assert "input" not in result.json()["error"]["details"][0]
    result = admin.post("/api/v1/admin/groups", json={"name": "bad", "allow_actions": ["*"]})
    assert result.status_code == 422


def test_ordinary_user_not_admin(app, admin):
    create_user(admin, allow_actions=["users.manage"])
    with TestClient(app) as client:
        login(client, "member")
        assert client.get("/api/v1/admin/users").status_code == 403
        assert client.post("/api/v1/admin/groups", json={"name": "x"}).status_code == 403
