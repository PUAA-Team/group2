"""Stage 19B-3：账号维度登录限流与产物上传并发保护。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import io
import json
import secrets
import struct
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from model_platform.database import utcnow
from model_platform.job_models import Job
from model_platform.models import LoginAttempt
from model_platform.security import digest
from model_platform.services.file_storage import resolve_key
from conftest import PASSWORD, create_user, login
from test_compute import enrollment, registration
from test_jobs import prepare, submit

ACCOUNT = "member"
IP_KEY = digest(f"{ACCOUNT}|testclient")
ACCOUNT_KEY = digest(f"account|{ACCOUNT}")


def _clear_ip_bucket(app):
    # 模拟换 IP：只清单 IP 桶，账号桶保持累计。
    with app.state.sessions() as db:
        row = db.get(LoginAttempt, IP_KEY)
        if row is not None:
            db.delete(row)
        db.commit()


def _wrong_login(client, account=ACCOUNT):
    return client.post("/api/v1/auth/login", json={"account": account, "password": "wrong"})


def _account_row(app):
    with app.state.sessions() as db:
        return db.get(LoginAttempt, ACCOUNT_KEY)


def test_account_lock_across_rotating_ips(app, admin):
    create_user(admin, account=ACCOUNT)
    with TestClient(app) as client:
        for index in range(15):
            result = _wrong_login(client)
            assert result.status_code == 401, result.text
            assert result.json()["error"]["code"] == "INVALID_CREDENTIALS"
            if index % 4 == 3:
                _clear_ip_bucket(app)
        # 单 IP 桶已被清空轮换，账号桶累计 15 次失败后整个账号被锁定。
        result = client.post("/api/v1/auth/login", json={"account": ACCOUNT, "password": PASSWORD})
        assert result.status_code == 429
        assert result.json()["error"]["code"] == "RATE_LIMITED"
        row = _account_row(app)
        assert row is not None and row.failures == 15
        assert row.blocked_until is not None
        # 锁定期过后恢复登录，且成功登录清掉账号桶。
        with app.state.sessions() as db:
            row = db.get(LoginAttempt, ACCOUNT_KEY)
            row.blocked_until = utcnow() - timedelta(seconds=1)
            db.commit()
        assert login(client, ACCOUNT).status_code == 200
        assert _account_row(app) is None


def test_account_window_slides(app, admin):
    create_user(admin, account=ACCOUNT)
    with TestClient(app) as client:
        for _ in range(3):
            assert _wrong_login(client).status_code == 401
        with app.state.sessions() as db:
            row = db.get(LoginAttempt, ACCOUNT_KEY)
            row.failures = 14
            row.window_started_at = utcnow() - timedelta(seconds=901)
            db.commit()
        # 窗口已过期：计数归零重新起计，本次失败只记 1 次，不触发锁定。
        assert _wrong_login(client).status_code == 401
        row = _account_row(app)
        assert row.failures == 1
        assert row.blocked_until is None


def test_success_clears_account_bucket(app, admin):
    create_user(admin, account=ACCOUNT)
    with TestClient(app) as client:
        for _ in range(3):
            assert _wrong_login(client).status_code == 401
        assert _account_row(app) is not None
        assert login(client, ACCOUNT).status_code == 200
        assert _account_row(app) is None


def _artifact_bytes(value):
    header = json.dumps({"weight": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
    raw = struct.pack("<Q", len(header)) + header + struct.pack("<f", value)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"format_version": 1, "trainer_id": "text-classifier-v1"}))
        archive.writestr("weights.safetensors", raw)
    return buffer.getvalue()


def _two_workers(app, admin, workspace):
    _, code = enrollment(admin, workspace)
    key = secrets.token_urlsafe(32)
    payload = registration(code, key)
    payload["inventory"]["runtime"]["trainers"] = ["text-classifier-v1"]
    clients = []
    for _ in range(2):
        worker = TestClient(app)
        result = worker.post("/api/worker/v1/register", json=payload)
        assert result.status_code == 200, result.text
        worker.headers["Authorization"] = "Bearer " + key
        clients.append(worker)
    return clients


def test_concurrent_artifact_uploads_keep_one(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    job = submit(admin, base, payload)
    workers = _two_workers(app, admin, workspace)
    try:
        lease = workers[0].post("/api/worker/v1/claim", json={}).json()["data"]
        assert lease["job_id"] == job["id"]
        eid = lease["execution_id"]
        path = f"/api/worker/v1/executions/{eid}"
        assert workers[0].post(path + "/events", json={"seq": 1, "type": "started", "payload": {}}).status_code == 200
        first = _artifact_bytes(1.0)
        second = _artifact_bytes(2.0)
        assert hashlib.sha256(first).hexdigest() != hashlib.sha256(second).hexdigest()

        def upload(client, content):
            return client.post(path + "/artifact", files={"file": ("artifact.zip", content)}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(upload, workers[0], first), pool.submit(upload, workers[1], second)]
            statuses = sorted(future.result() for future in results)
        # 并发双传：一个成功，一个冲突；落盘文件与数据库记录的摘要一致，不被覆盖。
        assert statuses == [200, 409], statuses
        with app.state.sessions() as db:
            stored = db.scalar(select(Job).where(Job.id == job["id"]))
            assert stored.artifact_sha256 in {hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest()}
            assert stored.artifact_key == f"{workspace}/artifacts/{eid}.zip"
        disk = resolve_key(app.state.settings, stored.artifact_key)
        assert hashlib.sha256(disk.read_bytes()).hexdigest() == stored.artifact_sha256
        # 幂等重传胜者产物仍成功，重传败者产物仍冲突。
        winner = first if stored.artifact_sha256 == hashlib.sha256(first).hexdigest() else second
        loser = second if winner is first else first
        assert workers[0].post(path + "/artifact", files={"file": ("artifact.zip", winner)}).status_code == 200
        assert workers[0].post(path + "/artifact", files={"file": ("artifact.zip", loser)}).status_code == 409
    finally:
        for worker in workers:
            worker.close()
