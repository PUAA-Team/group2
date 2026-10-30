from dataclasses import replace
import hashlib
import io
import json
import secrets
import struct
import zipfile

from fastapi.testclient import TestClient

from conftest import create_group, create_user, login
from test_compute import enrollment, registration


def prepare(app, admin, workspace):
    app.state.settings = replace(app.state.settings, max_samples=1000)
    base = f"/api/v1/workspaces/{workspace}"
    group = create_group(admin)
    me = admin.get("/api/v1/auth/session").json()["data"]["user"]
    result = admin.patch(f"/api/v1/admin/users/{me['id']}", headers={"If-Match": str(me["revision"])}, json={"group_id": group["id"]})
    assert result.status_code == 200, result.text
    result = admin.post(base + "/presets", json={"task_types": ["text_classification"]})
    assert result.status_code == 200, result.text
    options = admin.get(base + "/job-options").json()["data"]
    payload = {"name": "真实执行协议测试", "model_version_id": options["models"][0]["id"], "dataset_version_id": options["datasets"][0]["id"], "config": {"epochs": 2}}
    return base, payload


def node_client(app, admin, workspace):
    _, code = enrollment(admin, workspace)
    key = secrets.token_urlsafe(32)
    payload = registration(code, key)
    payload["inventory"]["runtime"]["trainers"] = ["text-classifier-v1"]
    worker = TestClient(app)
    result = worker.post("/api/worker/v1/register", json=payload)
    assert result.status_code == 200, result.text
    worker.headers["Authorization"] = "Bearer " + key
    return worker


def submit(admin, base, payload):
    result = admin.post(base + "/jobs", json=payload)
    assert result.status_code == 201, result.text
    job = result.json()["data"]
    result = admin.post(base + f"/jobs/{job['id']}/submit", headers={"If-Match": str(job["revision"])})
    assert result.status_code == 200, result.text
    return result.json()["data"]


def fake_artifact():
    header = json.dumps({"weight": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
    raw = struct.pack("<Q", len(header)) + header + struct.pack("<f", 1)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"format_version": 1, "trainer_id": "text-classifier-v1"}))
        archive.writestr("weights.safetensors", raw)
    return buffer.getvalue()


def test_snapshot_claim_events_artifact_and_idempotency(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    job = submit(admin, base, payload)
    assert job["snapshot"]["sha256"] and job["status"] == "queued"
    assert admin.patch(base + f"/jobs/{job['id']}", headers={"If-Match": "2"}, json=payload).status_code == 409
    with node_client(app, admin, workspace) as worker:
        lease = worker.post("/api/worker/v1/claim", json={}).json()["data"]
        assert lease["job_id"] == job["id"]
        eid = lease["execution_id"]; path = f"/api/worker/v1/executions/{eid}"
        assert worker.post("/api/worker/v1/claim", json={}).json()["data"]["execution_id"] == eid
        raw = worker.get(path + "/input")
        assert hashlib.sha256(raw.content).hexdigest() == job["snapshot"]["dataset_sha256"]
        event = {"seq": 1, "type": "started", "payload": {}}
        assert worker.post(path + "/events", json=event).status_code == 200
        assert worker.post(path + "/events", json=event).status_code == 200
        assert worker.post(path + "/events", json={**event, "payload": {"changed": True}}).status_code == 409
        assert worker.post(path + "/finish", json={"status": "succeeded"}).status_code == 409
        assert worker.post(path + "/artifact", files={"file": ("artifact.zip", fake_artifact())}).status_code == 200
        result = {"status": "succeeded", "result": {"accuracy": 0.5}}
        assert worker.post(path + "/finish", json=result).status_code == 200
        assert worker.post(path + "/finish", json=result).status_code == 200
        assert worker.post(path + "/finish", json={"status": "failed"}).status_code == 409
    latest = admin.get(base + f"/jobs/{job['id']}").json()["data"]
    assert latest["output_model_version_id"] and "artifact_key" not in latest
    assert admin.get(base + f"/jobs/{job['id']}/events").json()["data"][0]["seq"] == 1


def test_cancel_stop_and_retry_keep_old_snapshot(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    first = submit(admin, base, payload)
    assert admin.post(base + f"/jobs/{first['id']}/stop").json()["data"]["status"] == "cancelled"
    second = submit(admin, base, payload)
    with node_client(app, admin, workspace) as worker:
        eid = worker.post("/api/worker/v1/claim", json={}).json()["data"]["execution_id"]
        assert admin.post(base + f"/jobs/{second['id']}/stop").json()["data"]["status"] == "stopping"
        assert worker.get(f"/api/worker/v1/executions/{eid}/control").json()["data"]["stop"]
        assert worker.post(f"/api/worker/v1/executions/{eid}/finish", json={"status": "failed"}).json()["data"]["status"] == "stopped"
    result = admin.post(base + f"/jobs/{second['id']}/retry")
    assert result.status_code == 201 and result.json()["data"]["id"] != second["id"]
    assert result.json()["data"]["status"] == "draft"


def test_zero_quota_does_not_start_and_viewer_cannot_submit(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    me = admin.get("/api/v1/auth/session").json()["data"]["user"]
    admin.patch(f"/api/v1/admin/users/{me['id']}", headers={"If-Match": str(me["revision"])}, json={"quota": {"concurrent_jobs": 0}})
    submit(admin, base, payload)
    with node_client(app, admin, workspace) as worker:
        assert worker.post("/api/worker/v1/claim", json={}).json()["data"] is None
    group = admin.get("/api/v1/admin/groups").json()["data"][0]
    user = create_user(admin, group_id=group["id"])
    admin.post(base + "/members", json={"user_id": user["id"], "role": "viewer"})
    with TestClient(app) as member:
        login(member, "member")
        access = member.get(base + "/access").json()["data"]["actions"]
        assert "training.write" not in access and "services.invoke" not in access
        assert member.post(base + "/jobs", json=payload).status_code == 403


def test_invalid_and_cross_workspace_inputs_are_rejected(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    other = admin.post("/api/v1/workspaces", json={"name": "其他空间"}).json()["data"]["id"]
    assert admin.post(f"/api/v1/workspaces/{other}/jobs", json=payload).status_code == 422
    assert admin.post(base + "/jobs", json={**payload, "config": {"learning_rate": 99}}).status_code == 422
    assert admin.post(base + "/jobs", json={**payload, "kind": "service", "dataset_version_id": None}).status_code == 422


def test_image_zip_validation_rejects_traversal_and_bad_images():
    from model_platform.services.image_files import image_rows
    from model_platform.errors import Problem
    for filename in ("../escape.png", "images/bad.png"):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as archive:
            archive.writestr(filename, b"not-image")
            archive.writestr("labels.csv", "filename,label\n" + filename + ",a\n")
        try:
            image_rows(raw.getvalue(), 10)
        except Problem as error:
            assert error.status == 422
        else:
            raise AssertionError("不安全的图像 ZIP 被接受")
