from copy import deepcopy
from datetime import timedelta
import hashlib
import re
import secrets

from fastapi.testclient import TestClient
from sqlalchemy import select

from conftest import create_group, create_user, login
from model_platform.compute_models import ComputeDevice, ComputeNode, Enrollment
from model_platform.database import utcnow


def enrollment(admin, workspace, **changes):
    payload = {"workspace_id": workspace, "name": "GPU 测试节点", "platform": "linux", "controller_url": "http://127.0.0.1:8000",
               "state_dir": "/tmp/worker-test", "auto_approve": True}
    payload.update(changes)
    result = admin.post("/api/v1/admin/enrollments", json=payload)
    assert result.status_code == 201, result.text
    data = result.json()["data"]
    code = re.search(r"enr_[a-f0-9]{32}\.[A-Za-z0-9_-]+", data["command"]).group()
    return data, code


def registration(code, key, **changes):
    value = {"protocol_version": 1, "join_code": code, "installation_id": "00000000-0000-0000-0000-000000000001",
             "machine_id": "a" * 64, "credential_digest": hashlib.sha256(key.encode()).hexdigest(), "slots": 2,
             "inventory": {"hostname": "test-machine", "platform": "Windows", "cpu_count": 8, "memory_mb": 16000,
                           "runtime": {"torch_version": "test", "cuda_available": True},
                           "devices": [{"uuid": "cpu-test", "kind": "cpu", "name": "CPU", "memory_mb": 16000},
                                       {"uuid": "GPU-test", "kind": "cuda", "name": "RTX test", "memory_mb": 8000, "utilization": 20, "used_memory_mb": 400, "driver": "test"}]}}
    value.update(changes)
    return value


def test_register_heartbeat_probe_and_no_secret_disclosure(app, admin, workspace):
    receipt, code = enrollment(admin, workspace)
    assert code not in receipt["display_command"] and "<一次性接入码>" in receipt["display_command"]
    key = secrets.token_urlsafe(32)
    payload = registration(code, key)
    with TestClient(app) as worker:
        result = worker.post("/api/worker/v1/register", json=payload)
        assert result.status_code == 200, result.text
        node_id = result.json()["data"]["node_id"]
        assert worker.post("/api/worker/v1/register", json=payload).json()["data"]["node_id"] == node_id
        assert worker.post("/api/worker/v1/register", json={**payload, "credential_digest": "0" * 64}).status_code == 409
        worker.headers["Authorization"] = f"Bearer {key}"
        beat = {"protocol_version": 1, "seq": 1, "active_executions": [], "metrics": payload["inventory"]["devices"]}
        assert worker.post("/api/worker/v1/heartbeat", json=beat).status_code == 200
        assert worker.post("/api/worker/v1/heartbeat", json=beat).status_code == 200
        assert worker.post("/api/worker/v1/heartbeat", json={**beat, "active_executions": ["different"]}).status_code == 409
        probe = admin.post(f"/api/v1/resources/nodes/{node_id}/probe").json()["data"]["request_id"]
        controls = worker.post("/api/worker/v1/heartbeat", json={**beat, "seq": 2}).json()["data"]
        assert controls["probe_request_id"] == probe
        assert worker.post("/api/worker/v1/inventory", json={"request_id": probe, "inventory": payload["inventory"]}).status_code == 200
        assert worker.post("/api/worker/v1/inventory", json={"request_id": probe, "inventory": payload["inventory"]}).status_code == 409
    nodes = admin.get("/api/v1/admin/nodes")
    assert nodes.status_code == 200, nodes.text
    assert nodes.json()["pagination"]["total"] == 1
    assert nodes.json()["data"][0]["status"] == "在线"
    assert "credential_digest" not in nodes.text and code not in nodes.text and key not in nodes.text
    assert admin.get(f"/api/v1/resources/enrollments/{receipt['id']}").json()["data"]["status"] == "已接入"


def test_expiry_revocation_invalid_credential_and_local_guard(app, admin, workspace):
    receipt, code = enrollment(admin, workspace)
    with app.state.sessions() as db:
        record = db.get(Enrollment, receipt["id"]); record.expires_at = utcnow() - timedelta(seconds=1); db.commit()
    with TestClient(app) as worker:
        assert worker.post("/api/worker/v1/register", json=registration(code, "key")).status_code == 401
        assert worker.post("/api/worker/v1/heartbeat", json={"protocol_version": 1, "seq": 1}).status_code == 401
    second, code = enrollment(admin, workspace)
    assert admin.post(f"/api/v1/resources/enrollments/{second['id']}/revoke").status_code == 200
    with TestClient(app) as worker:
        assert worker.post("/api/worker/v1/register", json=registration(code, "key")).status_code == 401
    assert admin.post("/api/v1/admin/local-worker", json={"workspace_id": workspace}).status_code == 403


def test_space_visibility_approval_and_no_release_on_disconnect(app, admin, workspace):
    receipt, code = enrollment(admin, workspace, auto_approve=False)
    key = secrets.token_urlsafe(32)
    with TestClient(app) as worker:
        node_id = worker.post("/api/worker/v1/register", json=registration(code, key)).json()["data"]["node_id"]
    assert admin.get(f"/api/v1/resources/nodes/{node_id}").json()["data"]["status"] == "待审核"
    assert admin.patch(f"/api/v1/resources/nodes/{node_id}", json={"approved": True}, headers={"If-Match": '"1"'}).status_code == 200
    with app.state.sessions() as db:
        node = db.get(ComputeNode, node_id); node.last_seen_at = utcnow() - timedelta(seconds=60)
        device = db.scalar(select(ComputeDevice).where(ComputeDevice.node_id == node_id, ComputeDevice.kind == "cuda"))
        device.reserved_execution_id = "exe_pending"
        db.commit()
    details = admin.get(f"/api/v1/resources/nodes/{node_id}").json()["data"]
    assert details["status"] == "离线"
    assert any(device["status"] == "失联占用" and device["reserved_execution_id"] == "exe_pending" for device in details["devices"])
    assert admin.post(f"/api/v1/resources/nodes/{node_id}/revoke").status_code == 409
    group = create_group(admin)
    user = create_user(admin, group_id=group["id"])
    with TestClient(app) as client:
        login(client, "member")
        assert client.get(f"/api/v1/resources/nodes/{node_id}").status_code == 404
        admin.post(f"/api/v1/workspaces/{workspace}/members", json={"user_id": user["id"], "role": "viewer"})
        assert client.get(f"/api/v1/resources/nodes/{node_id}").status_code == 200
        assert client.post(f"/api/v1/resources/nodes/{node_id}/probe").status_code == 403


def test_bundle_contains_only_worker_source(admin):
    import io, zipfile
    response = admin.get("/api/worker/v1/bundle")
    assert response.status_code == 200
    assert response.headers["X-Content-SHA256"] == hashlib.sha256(response.content).hexdigest()
    sha = response.headers["X-Content-SHA256"]
    assert admin.get("/api/worker/v1/bundle?sha256=" + sha).content == response.content
    assert admin.get("/api/worker/v1/bundle?sha256=../../private").status_code == 422
    assert admin.get("/api/worker/v1/bundle?sha256=" + "0" * 64).status_code == 404
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "training_worker/agent.py" in archive.namelist()
        assert all(name.endswith(".py") for name in archive.namelist())
        assert not any("node-state" in name or "test" in name or "__pycache__" in name for name in archive.namelist())
