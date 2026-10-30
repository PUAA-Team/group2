import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from model_platform.cli import bootstrap_admin, migrate
from model_platform.config import Settings
from model_platform.main import create_app
from conftest import PASSWORD


def test_empty_runtime_environment_uses_documented_default(monkeypatch):
    monkeypatch.setenv("MT_RUNTIME_DIR", "")
    if os.name == "nt":
        assert Settings().runtime_dir.as_posix() == "D:/model-training-demo/backend-runtime"
    else:
        # Linux部署必须提供绝对目录，防止把Windows路径作为相对目录写入。
        with pytest.raises(ValueError, match="MT_RUNTIME_DIR"):
            Settings()


def test_no_implicit_schema_and_ready_after_explicit_migration(settings):
    app = create_app(settings)
    try:
        assert not (settings.runtime_dir / "platform.sqlite3").exists()
        with TestClient(app) as client:
            assert client.get("/healthz").status_code == 200
            assert client.get("/readyz").status_code == 503
        assert not (settings.runtime_dir / "platform.sqlite3").exists()
        migrate(settings)
        with TestClient(app) as client:
            assert client.get("/readyz").status_code == 200
        assert "dataset_versions" in inspect(app.state.engine).get_table_names()
        migrate(settings)  # 升级重复执行保持已有数据。
        bootstrap_admin(settings, "owner", "测试管理员", PASSWORD)
        try:
            bootstrap_admin(settings, "another", "第二管理员", PASSWORD)
        except ValueError:
            pass
        else:
            raise AssertionError("初始化不能覆盖已有管理员")
    finally:
        app.state.engine.dispose()


def test_request_id_and_runtime_openapi(app, admin):
    result = admin.get("/healthz", headers={"X-Request-ID": "untrusted-client"})
    assert result.json()["request_id"] == result.headers["x-request-id"]
    assert result.headers["x-request-id"] != "untrusted-client"
    schema = app.openapi()
    ids = [operation["operationId"] for path in schema["paths"].values()
           for method, operation in path.items() if method in {"get", "post", "patch"}]
    assert len(ids) == len(set(ids)) and len(ids) >= 33
    assert any(path.endswith("/jobs") for path in schema["paths"])
    assert not any("/assistant-requests" in path for path in schema["paths"])
    assert schema["components"]["schemas"]["ModelCreate"]["additionalProperties"] is False
    assert "password_hash" not in schema["components"]["schemas"]["UserOut"]["properties"]
    assert "storage_key" not in schema["components"]["schemas"]["DatasetVersionOut"]["properties"]
    assert schema["components"]["securitySchemes"]["APIKeyCookie"]["in"] == "cookie"
    assert schema["paths"]["/api/v1/admin/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"].get("$ref")
    validation_schema = schema["paths"]["/api/v1/admin/users"]["post"]["responses"]["422"]["content"]["application/json"]["schema"]
    assert validation_schema == {"$ref": "#/components/schemas/ErrorEnvelope"}


def test_request_body_cap(admin):
    result = admin.post("/api/v1/workspaces", content=b"x" * (65536 + 2049), headers={"Content-Type": "application/json"})
    assert result.status_code == 413
    assert result.json()["request_id"] == result.headers["x-request-id"]


def test_unexpected_error_does_not_escape_to_host_logs(app, monkeypatch, caplog):
    def broken_session():
        raise RuntimeError("private-content-must-not-be-logged")
    monkeypatch.setattr(app.state, "sessions", broken_session)
    with TestClient(app) as client:
        result = client.get("/api/v1/auth/session")
    assert result.status_code == 500
    assert result.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-content" not in result.text + caplog.text
