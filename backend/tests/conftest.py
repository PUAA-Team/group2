from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from model_platform.cli import bootstrap_admin, migrate
from model_platform.config import Settings
from model_platform.main import create_app
from model_platform.permissions import ACTIONS

PASSWORD = "test-only-password-2026"


@pytest.fixture
def settings(tmp_path):
    assert Path(tmp_path).drive.upper() != "C:", "测试运行文件必须放 D 盘"
    return Settings(runtime_dir=tmp_path, max_upload_bytes=2048, max_samples=3)


@pytest.fixture
def app(settings):
    migrate(settings)
    bootstrap_admin(settings, "owner", "测试管理员", PASSWORD)
    application = create_app(settings)
    yield application
    application.state.engine.dispose()


def login(client, account="owner"):
    result = client.post("/api/v1/auth/login", json={"account": account, "password": PASSWORD})
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["data"]["csrf_token"]
    return result


@pytest.fixture
def admin(app):
    with TestClient(app) as client:
        login(client)
        yield client


@pytest.fixture
def workspace(admin):
    result = admin.post("/api/v1/workspaces", json={"name": "开发空间"})
    assert result.status_code == 201, result.text
    return result.json()["data"]["id"]


def create_group(admin, **changes):
    payload = {"name": "研发组", "allow_actions": sorted(ACTIONS - {"users.manage", "groups.manage"}),
               "quota": {"gpu_count": 2, "concurrent_jobs": 3, "storage_gib": 50}}
    payload.update(changes)
    result = admin.post("/api/v1/admin/groups", json=payload)
    assert result.status_code == 201, result.text
    return result.json()["data"]


def create_user(admin, account="member", **changes):
    payload = {"account": account, "display_name": account, "password": PASSWORD}
    payload.update(changes)
    result = admin.post("/api/v1/admin/users", json=payload)
    assert result.status_code == 201, result.text
    return result.json()["data"]


def model_payload(**changes):
    payload = {"name": "文本模型", "task_type": "text_classification",
               "trainer_id": "text-classifier-v1", "source_ref": "team/text-model"}
    payload.update(changes)
    return payload
