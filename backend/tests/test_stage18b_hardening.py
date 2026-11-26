import io
from contextlib import ExitStack
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from conftest import PASSWORD, login, model_payload
from test_device_purposes import attach, claim, data


def test_lease_expiration_reclaims_device_and_allows_next_claim(app, admin, workspace):
    from model_platform.compute_models import ComputeDevice
    from model_platform.database import utcnow
    from model_platform.job_models import Execution
    from model_platform.models import User, UserGroup

    from dataclasses import replace
    app.state.settings = replace(app.state.settings, max_samples=20)
    with app.state.sessions() as db:
        owner = db.scalar(select(User).where(User.account == "owner"))
        group = db.get(UserGroup, owner.group_id)
        group.quota = {**group.quota, "concurrent_jobs": 2}
        db.commit()

    ds = data(admin.post(f"/api/v1/workspaces/{workspace}/datasets", json={"name": "租约数据集", "task_type": "text_classification", "description": ""}), 201)
    ver = data(admin.post(f"/api/v1/workspaces/{workspace}/datasets/{ds['id']}/versions", files={"file": ("train.csv", io.BytesIO(b"text,label\na,pos\nb,pos\nc,neg\nd,neg\n"))}), 201)
    mdl = data(admin.post(f"/api/v1/workspaces/{workspace}/models", json=model_payload(name="租约模型")), 201)
    mver = data(admin.post(f"/api/v1/workspaces/{workspace}/models/{mdl['id']}/versions", json={"version": "v1", "source_ref": "builtin://text-linear-v1"}), 201)

    job1 = data(admin.post(f"/api/v1/workspaces/{workspace}/jobs", json={"name": "超时任务", "kind": "train", "model_version_id": mver["id"], "dataset_version_id": ver["id"], "device_kind": "cpu"}), 201)
    data(admin.post(f"/api/v1/workspaces/{workspace}/jobs/{job1['id']}/submit", headers={"If-Match": str(job1["revision"])}))

    with ExitStack() as stack:
        worker, node_id, _ = attach(app, admin, workspace, stack, "lease-node")
        claimed1 = claim(worker)
        assert claimed1["job_id"] == job1["id"]

        # 模拟 Worker 失联且租约超时
        with app.state.sessions() as db:
            exe = db.get(Execution, claimed1["execution_id"])
            exe.lease_until = utcnow() - timedelta(seconds=5)
            db.commit()

        # 提交第二个任务并由同一节点 claim，应先回收过期租约再领取新任务
        job2 = data(admin.post(f"/api/v1/workspaces/{workspace}/jobs", json={"name": "恢复任务", "kind": "train", "model_version_id": mver["id"], "dataset_version_id": ver["id"], "device_kind": "cpu"}), 201)
        data(admin.post(f"/api/v1/workspaces/{workspace}/jobs/{job2['id']}/submit", headers={"If-Match": str(job2["revision"])}))

        claimed2 = claim(worker)
        assert claimed2 is not None and claimed2["job_id"] == job2["id"]

        j1_after = data(admin.get(f"/api/v1/workspaces/{workspace}/jobs/{job1['id']}"))
        assert j1_after["status"] == "failed"
        assert "超时" in (j1_after["error"] or "")

        with app.state.sessions() as db:
            dev = db.scalar(select(ComputeDevice).where(ComputeDevice.node_id == node_id))
            assert dev.reserved_execution_id == claimed2["execution_id"]


def test_retry_idempotency_and_lock_batch_cas(app, admin, workspace):
    from model_platform.data_models import AnnotationBatch
    from model_platform.errors import Problem
    from model_platform.services.annotations import lock_batch

    ds = data(admin.post(f"/api/v1/workspaces/{workspace}/datasets", json={"name": "CAS数据集", "task_type": "text_classification", "description": ""}), 201)
    ver = data(admin.post(f"/api/v1/workspaces/{workspace}/datasets/{ds['id']}/versions", files={"file": ("train.csv", io.BytesIO(b"text,label\na,pos\nb,neg\n"))}), 201)
    mdl = data(admin.post(f"/api/v1/workspaces/{workspace}/models", json=model_payload(name="CAS模型")), 201)
    mver = data(admin.post(f"/api/v1/workspaces/{workspace}/models/{mdl['id']}/versions", json={"version": "v1", "source_ref": "builtin://text-linear-v1"}), 201)

    job = data(admin.post(f"/api/v1/workspaces/{workspace}/jobs", json={"name": "已取消任务", "kind": "train", "model_version_id": mver["id"], "dataset_version_id": ver["id"], "device_kind": "cpu"}), 201)
    job = data(admin.post(f"/api/v1/workspaces/{workspace}/jobs/{job['id']}/stop"))
    assert job["status"] == "cancelled"

    # 幂等重试：携带相同 Idempotency-Key 只创建一次草稿
    r1 = admin.post(f"/api/v1/workspaces/{workspace}/jobs/{job['id']}/retry", headers={"Idempotency-Key": "idem-1"})
    r2 = admin.post(f"/api/v1/workspaces/{workspace}/jobs/{job['id']}/retry", headers={"Idempotency-Key": "idem-1"})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["data"]["id"] == r2.json()["data"]["id"]

    # lock_batch 过期 revision 必须报错 409 CONFLICT
    batch = data(admin.post(f"/api/v1/workspaces/{workspace}/annotation-batches", json={"name": "并发批次", "version_id": ver["id"], "labels": ["pos", "neg"]}), 201)
    with app.state.sessions() as db:
        from sqlalchemy import update
        b = db.get(AnnotationBatch, batch["id"])
        with app.state.sessions() as other_db:
            other_db.execute(update(AnnotationBatch).where(AnnotationBatch.id == b.id).values(revision=b.revision + 5))
            other_db.commit()
        with pytest.raises(Problem) as exc:
            lock_batch(db, b)
        assert exc.value.status == 409


def test_multi_session_list_and_revoke(app):
    c1 = TestClient(app)
    c2 = TestClient(app)
    c3 = TestClient(app)
    login(c1, "owner")
    login(c2, "owner")
    login(c3, "owner")

    listed = data(c1.get("/api/v1/auth/sessions"))
    assert len(listed) == 3
    assert sum(1 for item in listed if item["current"]) == 1

    others = [item for item in listed if not item["current"]]
    rev_one = data(c1.delete(f"/api/v1/auth/sessions/{others[0]['id']}"))
    assert rev_one["revoked"] is True and rev_one["current"] is False

    listed_after = data(c1.get("/api/v1/auth/sessions"))
    assert len(listed_after) == 2

    rev_rest = data(c1.post("/api/v1/auth/sessions/revoke-others"))
    assert rev_rest["revoked"] == 1
    assert c1.get("/api/v1/auth/session").status_code == 200
    assert c2.get("/api/v1/auth/session").status_code == 401
    assert c3.get("/api/v1/auth/session").status_code == 401
