from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import timedelta
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from conftest import create_user, login
from model_platform.compute_models import ComputeDevice, ComputeNode
from model_platform.database import utcnow
from model_platform.job_models import Job
from test_device_purposes import attach, claim, data
from test_jobs import prepare, submit


def seed_queue(app, job_id, rows):
    with app.state.sessions() as db:
        job = db.get(Job, job_id)
        template = {column.name: getattr(job, column.name) for column in Job.__table__.columns}
        db.execute(insert(Job.__table__), [{**template, **row} for row in rows])
        db.commit()


def test_cpu_claim_skips_gpu_head_and_preserves_order(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    original = submit(admin, base, payload)
    start = utcnow() - timedelta(hours=1)
    blocked = [{"id": f"job_gpu_{i:03}", "device_kind": "cuda", "priority": 10, "created_at": start}
               for i in range(210)]
    compatible = [{"id": "job_cpu_low", "priority": 1, "created_at": start},
                  {"id": "job_cpu_b", "priority": 2, "created_at": start},
                  {"id": "job_cpu_a", "priority": 2, "created_at": start},
                  {"id": "job_cpu_newer", "priority": 2, "created_at": start + timedelta(seconds=1)}]
    seed_queue(app, original["id"], blocked + compatible)
    with ExitStack() as stack:
        worker, _, _ = attach(app, admin, workspace, stack, "CPU 节点")
        for job_id in ("job_cpu_a", "job_cpu_b", "job_cpu_newer", "job_cpu_low", original["id"]):
            assignment = claim(worker)
            assert assignment is not None and assignment["job_id"] == job_id
            path = f"/api/worker/v1/executions/{assignment['execution_id']}"
            data(worker.post(path + "/finish", json={"status": "failed", "error": "验收后释放"}))
        assert claim(worker) is None


def test_blocked_user_does_not_hide_eligible_tasks_in_later_batches(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    job = submit(admin, base, payload)
    owner = data(admin.get("/api/v1/auth/session"))["user"]
    blocked = create_user(admin, account="blocked", group_id=owner["group_id"], quota={"concurrent_jobs": 0})
    data(admin.post(base + "/members", json={"user_id": blocked["id"], "role": "editor"}))
    start = utcnow() - timedelta(hours=1)
    seed_queue(app, job["id"], [
        {"id": f"job_zero_quota_{i:03}", "priority": 10, "created_at": start, "created_by": blocked["id"]}
        for i in range(201)
    ])
    with ExitStack() as stack:
        worker, _, _ = attach(app, admin, workspace, stack, "后排领取")
        assignment = claim(worker)
        assert assignment is not None and assignment["job_id"] == job["id"]


def test_two_workers_claim_once_and_recover_existing_assignment(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    job = submit(admin, base, payload)
    with ExitStack() as stack, ThreadPoolExecutor(max_workers=2) as pool:
        workers = [attach(app, admin, workspace, stack, name) for name in ("测试节点甲", "测试节点乙")]
        barrier = Barrier(2, timeout=10)

        def take(entry):
            barrier.wait()
            return claim(entry[0])

        results = list(pool.map(take, workers))
        assert sum(item is not None for item in results) == 1
        index = next(i for i, item in enumerate(results) if item)
        assignment = results[index]
        worker, node_id, _ = workers[index]
        assert assignment["job_id"] == job["id"]
        with app.state.sessions() as db:
            db.get(ComputeNode, node_id).last_seen_at = utcnow() - timedelta(minutes=10)
            db.commit()
        recovered = claim(worker)
        assert recovered["redelivered"] and recovered["execution_id"] == assignment["execution_id"]
        assert claim(workers[1 - index][0]) is None


def test_resource_summary_is_scoped_and_keeps_disconnected_reservations(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    job = submit(admin, base, payload)
    other = data(admin.post("/api/v1/workspaces", json={"name": "其他资源空间"}), 201)["id"]
    owner = data(admin.get("/api/v1/auth/session"))["user"]
    viewer = create_user(admin, group_id=owner["group_id"])
    data(admin.post(base + "/members", json={"user_id": viewer["id"], "role": "viewer"}))
    with ExitStack() as stack:
        worker, node_id, _ = attach(app, admin, workspace, stack, "失联节点")
        attach(app, admin, workspace, stack, "空闲节点")
        attach(app, admin, other, stack, "其他空间节点")
        assert claim(worker)["job_id"] == job["id"]
        with app.state.sessions() as db:
            db.get(ComputeNode, node_id).last_seen_at = utcnow() - timedelta(minutes=10)
            db.scalar(select(ComputeDevice).where(ComputeDevice.node_id == node_id)).present = False
            db.commit()
        viewer_client = stack.enter_context(TestClient(app))
        login(viewer_client, "member")
        assert viewer_client.get(f"/api/v1/workspaces/{other}/resources?include_summary=true").status_code == 404
        assert viewer_client.get("/api/v1/admin/nodes?include_summary=true").status_code == 403
        listing = viewer_client.get(base + "/resources", params={"include_summary": "true", "page_size": 1, "q": "空闲节点"})
        assert len(data(listing)) == 1
        assert listing.json()["summary"] == {"nodes": {"total": 2, "online": 1},
            "cpu": {"total": 2, "occupied": 1, "disconnected_occupied": 1},
            "cuda": {"total": 0, "occupied": 0, "disconnected_occupied": 0}}
        overview = admin.get("/api/v1/admin/nodes?include_summary=true&page_size=1")
        data(overview)
        assert overview.json()["summary"]["nodes"] == {"total": 3, "online": 2}
        assert overview.json()["summary"]["cpu"]["total"] == 3
        assert admin.get("/api/v1/admin/nodes").json().get("summary") is None


def test_queue_detail_distinguishes_hardware_runtime_and_busy(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    with ExitStack() as stack:
        worker, node_id, _ = attach(app, admin, workspace, stack, "诊断节点")
        gpu = submit(admin, base, {**payload, "device_kind": "cuda"})
        assert gpu["queue_reason"] == "等待可见且规格匹配的设备"
        queued = submit(admin, base, payload)
        with app.state.sessions() as db:
            node = db.get(ComputeNode, node_id)
            original = node.inventory
            node.inventory = {**original, "runtime": {**original["runtime"], "trainers": []}}
            db.commit()
        path = base + f"/jobs/{queued['id']}"
        assert data(admin.get(path))["queue_reason"] == "等待兼容的 Worker 运行环境"
        assert claim(worker) is None
        with app.state.sessions() as db:
            db.get(ComputeNode, node_id).inventory = original
            db.commit()
        assert claim(worker)["job_id"] == queued["id"]
        waiting = submit(admin, base, payload)
        assert waiting["queue_reason_code"] == "no_available_device"
        assert waiting["queue_reason"] == "等待设备或节点槽位释放"
