from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import re

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD, create_group, create_user, login, model_payload
from model_platform.cli import migrate
from model_platform.main import create_app


def test_web_assets_do_not_expose_workspace_files(app):
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        entry = re.search(r'src="(/live/app\.js\?v=[^\"]+)"', client.get("/").text)
        assert entry, "真实前端入口必须带缓存版本"
        script = client.get(entry.group(1))
        assert script.status_code == 200 and 'javascript' in script.headers['content-type']
        for path in ["/live/app.js", "/styles/base.css", "/js/ui.js"]:
            assert client.get(path).status_code == 200
        for path in ["/backend/src/model_platform/config.py", "/docs/stage5/ReadMe.md", "/storage/file", "/live/../backend/requirements.txt"]:
            assert client.get(path).status_code == 404


def test_local_first_setup_then_login(settings):
    settings = replace(settings, allow_browser_setup=True)
    migrate(settings)
    app = create_app(settings)
    try:
        with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 41234)) as client:
            assert client.get("/api/v1/setup").json()["data"] == {"initialized": False, "enabled": True}
            payload = {"account": "Admin", "display_name": "管理员", "password": PASSWORD}
            result = client.post("/api/v1/setup", json=payload, headers={"Origin": "http://127.0.0.1:8000"})
            assert result.status_code == 201, result.text
            assert result.json()["data"]["account"] == "admin"
            assert "password" not in result.text
            assert client.get("/api/v1/setup").json()["data"] == {"initialized": True, "enabled": False}
            assert client.post("/api/v1/setup", json=payload).status_code == 409
            login(client, "admin")
            assert "workspaces.create" in client.get("/api/v1/auth/session").json()["data"]["access"]["actions"]
    finally:
        app.state.engine.dispose()


@pytest.mark.parametrize("enabled,host,client_ip", [(False, "127.0.0.1", "127.0.0.1"), (True, "evil.example", "127.0.0.1"), (True, "127.0.0.1", "203.0.113.1")])
def test_setup_guard(settings, enabled, host, client_ip):
    settings = replace(settings, allow_browser_setup=enabled)
    migrate(settings)
    app = create_app(settings)
    try:
        with TestClient(app, base_url=f"http://{host}:8000", client=(client_ip, 41234)) as client:
            assert client.get("/api/v1/setup").json()["data"]["enabled"] is False
            assert client.post("/api/v1/setup", json={"account": "owner", "display_name": "x", "password": PASSWORD}).status_code == 403
    finally:
        app.state.engine.dispose()


def test_setup_rejects_policy_injection_and_blank_name(settings):
    settings = replace(settings, allow_browser_setup=True)
    migrate(settings)
    app = create_app(settings)
    try:
        with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 41234)) as client:
            payload = {"account": "owner", "display_name": "x", "password": PASSWORD}
            assert client.post("/api/v1/setup", json={**payload, "is_admin": False}).status_code == 422
            assert client.post("/api/v1/setup", json={**payload, "display_name": " "}).status_code == 422
            assert client.post("/api/v1/setup", json=payload, headers={"Origin": "https://evil.example"}).status_code == 403
    finally:
        app.state.engine.dispose()


def test_concurrent_first_setup_creates_only_one_admin(settings):
    settings = replace(settings, allow_browser_setup=True)
    migrate(settings)
    app = create_app(settings)
    try:
        def initialize(account):
            with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 41234)) as client:
                return client.post("/api/v1/setup", json={"account": account, "display_name": account, "password": PASSWORD}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(initialize, "first-admin")
            second = pool.submit(initialize, "second-admin")
            assert sorted([first.result(), second.result()]) == [201, 409]
    finally:
        app.state.engine.dispose()


def test_member_names_roles_and_account_input(app, admin, workspace):
    group = create_group(admin)
    user = create_user(admin, group_id=group["id"])
    path = f"/api/v1/workspaces/{workspace}/members"
    assert admin.post(path, json={"account": "MEMBER", "role": "viewer"}).status_code == 200
    rows = admin.get(path).json()["data"]
    assert any(row["account"] == "member" and row["role"] == "viewer" for row in rows)
    assert admin.post(path, json={"user_id": user["id"], "account": "member", "role": "editor"}).status_code == 422
    with TestClient(app) as client:
        login(client, "member")
        assert client.get(path).status_code == 403
        access = client.get("/api/v1/auth/session").json()["data"]["access"]
        assert "datasets.read" in access["actions"]


def test_search_literal_percent_and_space_isolation(app, admin, workspace):
    path = f"/api/v1/workspaces/{workspace}"
    assert admin.post(path + "/models", json=model_payload(name="Coverage100%_model")).status_code == 201
    assert admin.post(path + "/models", json=model_payload(name="unrelated")).status_code == 201
    assert admin.get(path + "/models", params={"q": "%_"}).json()["pagination"]["total"] == 1
    assert admin.get(path + "/models", params={"q": "COVERAGE"}).json()["pagination"]["total"] == 1
    create_user(admin)
    assert admin.get("/api/v1/admin/users", params={"q": "member"}).json()["pagination"]["total"] == 1
    with TestClient(app) as client:
        login(client, "member")
        assert client.get(path + "/models", params={"q": "Coverage"}).status_code == 404
