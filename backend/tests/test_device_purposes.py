from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import timedelta
import secrets
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient

from conftest import create_user, login
from model_platform.compute_models import ComputeNode
from model_platform.database import utcnow
from test_compute import enrollment, registration
from test_jobs import fake_artifact, prepare, submit


def data(result, status=200):
    assert result.status_code == status, result.text
    return result.json()["data"]


def attach(app, admin, workspace, stack, name):
    _, code = enrollment(admin, workspace, name=name)
    key = secrets.token_urlsafe(32)
    payload = registration(code, key, installation_id=str(uuid4()), machine_id=secrets.token_hex(32))
    payload["inventory"]["runtime"]["trainers"] = ["text-classifier-v1"]
    payload["inventory"]["devices"] = payload["inventory"]["devices"][:1]
    worker = stack.enter_context(TestClient(app))
    node = data(worker.post("/api/worker/v1/register", json=payload))["node_id"]
    worker.headers["Authorization"] = "Bearer " + key
    device = data(admin.get(f"/api/v1/resources/nodes/{node}"))["devices"][0]["id"]
    return worker, node, f"/api/v1/resources/devices/{device}/policy"


def claim(worker, **body):
    return data(worker.post("/api/worker/v1/claim", json=body))


def test_dedicated_workers_do_not_cross_assign_and_release_on_finish(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    with ExitStack() as stack:
        train_worker, train_node, train_policy = attach(app, admin, workspace, stack, "训练节点")
        service_worker, service_node, service_policy = attach(app, admin, workspace, stack, "服务节点")
        assert data(admin.get(train_policy))["purpose"] == "shared"
        data(admin.post(train_policy, json={"revision": 0, "purpose": "train_eval"}))
        service_revision = data(admin.post(service_policy, json={"revision": 0, "purpose": "inference"}))["revision"]
        assert data(admin.post(service_policy, json={"revision": service_revision}))["purpose"] == "inference"
        assert admin.post(service_policy, json={"revision": 0, "purpose": "shared"}).status_code == 412

        for kind, expected in (("train", train_node), ("evaluate", train_node), ("service", service_node)):
            result = admin.get(base + "/resources", params={"job_kind": kind, "device_kind": "cpu", "page_size": 1})
            assert [row["id"] for row in data(result)] == [expected]
            assert result.json()["pagination"]["total"] == 1

        wrong = data(admin.post(base + "/jobs", json={**payload, "node_id": service_node}), 201)
        result = admin.post(base + f"/jobs/{wrong['id']}/submit", headers={"If-Match": str(wrong["revision"])})
        assert result.status_code == 409 and result.json()["error"]["code"] == "DEVICE_PURPOSE_MISMATCH"
        assert data(admin.get(base + f"/jobs/{wrong['id']}"))["status"] == "draft"

        job = submit(admin, base, payload)
        assert claim(service_worker) is None
        lease = claim(train_worker)
        assert lease["job_id"] == job["id"]
        result = admin.post(train_policy, json={"revision": 1, "purpose": "inference"})
        assert result.status_code == 409 and result.json()["error"]["code"] == "DEVICE_PURPOSE_IN_USE"
        execution = f"/api/worker/v1/executions/{lease['execution_id']}"
        data(train_worker.post(execution + "/events", json={"seq": 1, "type": "started", "payload": {}}))
        data(train_worker.post(execution + "/artifact", files={"file": ("artifact.zip", fake_artifact())}))
        assert data(train_worker.post(execution + "/finish", json={"status": "succeeded"}))["status"] == "succeeded"
        model = data(admin.get(base + f"/jobs/{job['id']}"))["output_model_version_id"]

        deploy = submit(admin, base, {**payload, "model_version_id": model, "kind": "service", "dataset_version_id": None})
        assert claim(train_worker) is None
        service_lease = claim(service_worker)
        assert service_lease["job_id"] == deploy["id"]
        evaluation = submit(admin, base, {**payload, "model_version_id": model, "kind": "evaluate"})
        assert claim(service_worker, known_executions=[service_lease["execution_id"]]) is None
        eval_lease = claim(train_worker)
        assert eval_lease["job_id"] == evaluation["id"]
        data(train_worker.post(f"/api/worker/v1/executions/{eval_lease['execution_id']}/finish",
                               json={"status": "succeeded", "result": {"accuracy": 0.5}}))
        service = f"/api/worker/v1/executions/{service_lease['execution_id']}"
        data(service_worker.post(service + "/events", json={"seq": 1, "type": "ready", "payload": {}}))
        assert data(admin.get(base + f"/jobs/{deploy['id']}"))["status"] == "ready"
        assert data(admin.post(base + f"/jobs/{deploy['id']}/stop"))["status"] == "stopping"
        assert data(service_worker.get(service + "/control"))["stop"]
        assert data(service_worker.post(service + "/finish", json={"status": "stopped"}))["status"] == "stopped"


def test_queue_reasons_acl_and_offline_reservation(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    with ExitStack() as stack:
        worker, node, policy = attach(app, admin, workspace, stack, "用途测试")
        owner = data(admin.get("/api/v1/auth/session"))["user"]
        member = create_user(admin, group_id=owner["group_id"])
        data(admin.post(base + "/members", json={"user_id": member["id"], "role": "viewer"}))
        member_client = stack.enter_context(TestClient(app))
        login(member_client, "member")
        data(admin.post(policy, json={"revision": 0, "purpose": "inference", "deny_users": [member["id"]]}))
        assert data(member_client.get(base + "/resources?job_kind=service")) == []
        visible = data(member_client.get(base + "/resources"))[0]["devices"][0]
        assert visible["selectable"] is False and "deny_users" not in visible
        assert member_client.post(policy, json={"revision": 1, "purpose": "shared"}).status_code == 403
        job = submit(admin, base, payload)
        assert job["queue_reason_code"] == "no_matching_purpose" and claim(worker) is None
        data(admin.post(policy, json={"revision": 1, "purpose": "train_eval"}))
        me = data(admin.get("/api/v1/auth/session"))["user"]
        headers = {"If-Match": str(me["revision"])}
        me = data(admin.patch(f"/api/v1/admin/users/{owner['id']}", headers=headers, json={"quota": {"concurrent_jobs": 0}}))
        assert data(admin.get(base + f"/jobs/{job['id']}"))["queue_reason_code"] == "quota_full"
        assert claim(worker) is None
        data(admin.patch(f"/api/v1/admin/users/{owner['id']}", headers={"If-Match": str(me["revision"])}, json={"quota": {}}))
        assert claim(worker)["job_id"] == job["id"]
        with app.state.sessions() as db:
            db.get(ComputeNode, node).last_seen_at = utcnow() - timedelta(minutes=10)
            db.commit()
        result = admin.post(policy, json={"revision": 2, "purpose": "shared"})
        assert result.status_code == 409 and result.json()["error"]["code"] == "DEVICE_PURPOSE_IN_USE"
        assert data(admin.get(base + "/resources?job_kind=train"))[0]["online"] is False
        assert submit(admin, base, payload)["queue_reason_code"] == "no_available_device"


def test_claim_and_purpose_change_cannot_both_succeed(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    job = submit(admin, base, payload)
    with ExitStack() as stack, ThreadPoolExecutor(max_workers=2) as pool:
        worker, _, policy = attach(app, admin, workspace, stack, "竞争测试")
        barrier = Barrier(2, timeout=10)

        def change():
            barrier.wait()
            return admin.post(policy, json={"revision": 0, "purpose": "inference"})

        def take():
            barrier.wait()
            return claim(worker)

        change_result, take_result = pool.submit(change), pool.submit(take)
        change_result, lease = change_result.result(), take_result.result()
        if lease:
            assert lease["job_id"] == job["id"]
            assert change_result.status_code == 409
            assert change_result.json()["error"]["code"] == "DEVICE_PURPOSE_IN_USE"
        else:
            assert data(change_result)["purpose"] == "inference"
            assert data(admin.get(base + f"/jobs/{job['id']}"))["queue_reason_code"] == "no_matching_purpose"
