"""云端控制、本机GPU执行的基础训练验收；凭据不写入公开结果。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import zipfile

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def wait(callback, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = callback()
            if value:
                return value
        except httpx.TransportError:
            pass
        time.sleep(1)
    raise RuntimeError("等待超时，保留现场后核对，不重复提交任务")


def handoff(root):
    from sqlalchemy import select
    from model_platform.compute_models import ComputeNode
    from model_platform.config import Settings
    from model_platform.database import make_engine, make_session_factory
    from model_platform.job_models import Execution, Job, ServiceKey
    from model_platform.models import User
    from model_platform.services.common import audit, commit
    from model_platform.services.compute import lock_node
    from model_platform.services.jobs import ACTIVE, stop_job
    from model_platform.services.local_worker import stop_local_worker
    from model_platform.services.process_state import process_alive

    settings = Settings(runtime_dir=Path("D:/model-training-demo/backend-runtime"),
                        database_url="sqlite:///D:/model-training-demo/backend-runtime/platform.sqlite3")
    engine = make_engine(settings.db_url)
    sessions = make_session_factory(engine)
    state = json.loads((settings.runtime_dir / "local-worker/node-state.json").read_text(encoding="utf-8"))
    target = "job_24866d2202e54a339cadb30cbeaf5bc2"
    try:
        previous = root / "local-handoff.json"
        if previous.exists():
            record = json.loads(previous.read_text(encoding="utf-8"))
            with sessions() as db:
                execution = db.scalar(select(Execution).where(Execution.job_id == target))
                journal = json.loads((settings.runtime_dir / "local-worker/executions" / execution.id / "journal.json").read_text(encoding="utf-8"))
                node = db.get(ComputeNode, record["node_id"])
                assert node.id == state["node_id"] and not node.enabled
            pids = [record["worker_pid"], journal["pid"]]
            assert all(isinstance(pid, int) and pid > 0 for pid in pids)
            query = " OR ".join(f"ProcessId={pid}" for pid in pids)
            check = subprocess.check_output(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                     f"@(Get-CimInstance Win32_Process -Filter '{query}' -ErrorAction Stop).Count"], text=True)
            if check.strip() != "0":
                raise ValueError("历史执行进程仍存在，停止自动交接")
            write(settings.runtime_dir / "local-worker/stop-request.json", {"reason": "cloud-handoff-processes-confirmed-absent"})
            record.update(worker_stopped=True, service_process_absent=True, old_reservation_preserved=True,
                          absent_process_ids=pids)
            write(previous, record)
            print("历史Worker及子进程已核实不存在；旧平台失联占用保留", flush=True)
            return
        with sessions() as db:
            node = db.get(ComputeNode, state["node_id"])
            lock_node(db, node)
            active = db.scalars(select(Job).join(Execution, Execution.job_id == Job.id)
                                .where(Execution.node_id == node.id, Job.status.in_(ACTIVE))).all()
            if any(job.id != target for job in active):
                raise ValueError("原节点存在其他活跃任务，停止自动交接")
            job = db.get(Job, target)
            actor = db.get(User, job.created_by)
            if not actor.active or not actor.is_admin:
                raise ValueError("原服务操作人不可用")
            if db.scalar(select(ServiceKey.id).where(ServiceKey.job_id == target, ServiceKey.revoked_at.is_(None)).limit(1)):
                raise ValueError("原服务存在有效API KEY，请先确认调用方")
            with sqlite3.connect(f"file:{settings.runtime_dir.as_posix()}/platform.sqlite3?mode=ro", uri=True) as source:
                with sqlite3.connect(root / "local-before-handoff.sqlite3") as backup:
                    source.backup(backup)
                    assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            record = {"node_id": node.id, "service_id": target, "was_enabled": node.enabled,
                      "actor_id": actor.id, "worker_pid": state["pid"]}
            write(root / "local-handoff.json", record)
            node.enabled = False
            node.revision += 1
            audit(db, actor, "resources.cloud.handoff", node.id, node.workspace_id)
            commit(db)
            stop_job(db, actor, job)

        def stopped():
            with sessions() as db:
                return db.get(Job, target).status == "stopped"

        wait(stopped)
        with sessions() as db:
            stop_local_worker(db, settings, db.get(User, record["actor_id"]))
        wait(lambda: not process_alive(state["pid"]), 30)
        record["service_stopped"] = record["worker_stopped"] = True
        write(root / "local-handoff.json", record)
        print("原Qwen服务及本机旧Worker已正常停止", flush=True)
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    if not root.is_relative_to(Path("D:/model-training-demo").resolve()):
        raise ValueError("验收数据必须位于D盘项目目录")
    if not arguments.resume:
        root.mkdir(parents=True, exist_ok=False)
    elif not (root / "verification.json").is_file():
        raise ValueError("没有可恢复的验收记录")
    credentials = json.loads(arguments.credentials.read_text(encoding="utf-8"))
    url = credentials["url"]
    if url != "https://47.93.115.188:5488":
        raise ValueError("目标控制端与本次授权服务器不一致")
    record = json.loads((root / "verification.json").read_text(encoding="utf-8")) if arguments.resume else {"url": url}
    assert record["url"] == url
    if record.get("job_id"):
        raise ValueError("已有训练任务，请先核查记录，不能重复提交")
    client = httpx.Client(base_url=url, trust_env=False, timeout=20)

    def api(method, path, **kwargs):
        response = client.request(method, "/api/v1" + path, **kwargs)
        if response.is_error:
            raise RuntimeError(f"接口未完成：{method} {path} {response.status_code} {response.text[:400]}")
        return response.json()["data"]

    def save():
        write(root / "verification.json", record)

    try:
        login = api("POST", "/auth/login", json={key: credentials[key] for key in ("account", "password")})
        client.headers["X-CSRF-Token"] = login["csrf_token"]
        user = login["user"]
        if not record.get("workspace_id"):
            group = api("POST", "/admin/groups", json={"name": "云端演示组", "quota": {"gpu_count": 1, "concurrent_jobs": 2, "storage_gib": 10}})
            api("PATCH", "/admin/users/" + user["id"], json={"group_id": group["id"]}, headers={"If-Match": f'"{user["revision"]}"'})
            workspace = api("POST", "/workspaces", json={"name": "云端演示空间"})
            record["workspace_id"] = workspace["id"]
            prefix = "/workspaces/" + workspace["id"]
            api("POST", prefix + "/presets", json={"task_types": ["text_classification", "image_classification", "llm_sft"]})
            project = api("POST", prefix + "/projects", json={"name": "服务器联调验收"})
            record["project_id"] = project["id"]
            save()
            print("云端账号额度、工作空间和三类预置已准备", flush=True)
        prefix = "/workspaces/" + record["workspace_id"]
        handoff(root)
        record["local_handoff_complete"] = True
        save()

        worker = root / "worker"
        worker.mkdir()
        python = "D:/model-training-demo/worker-llm-runtime/.venv/Scripts/python.exe"
        enrollment = api("POST", "/admin/enrollments", json={"workspace_id": record["workspace_id"], "name": "李旭笔记本 RTX 4060",
                         "platform": "windows", "controller_url": url, "training_python": python,
                         "state_dir": str(worker), "auto_approve": True})
        code = re.search(r"enr_[a-f0-9]{32}\.[A-Za-z0-9_-]+", enrollment["command"])
        if not code:
            raise ValueError("接入命令未包含预期的一次性码")
        bundle = client.get("/api/worker/v1/bundle", params={"sha256": enrollment["bundle_sha256"]})
        bundle.raise_for_status()
        assert hashlib.sha256(bundle.content).hexdigest() == enrollment["bundle_sha256"]
        bundle_path = worker / "worker.pyz"
        bundle_path.write_bytes(bundle.content)
        command = [python, "-B", str(bundle_path), "agent", "--controller", url, "--state-dir", str(worker),
                   "--trainer-python", python, "--slots", "2", "--join-code-stdin", "--model-cache",
                   "D:/model-training-demo/worker-llm-runtime/cache/huggingface"]
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
                       "NO_PROXY": "47.93.115.188,127.0.0.1,localhost"}
        with (worker / "worker.out.log").open("ab") as stdout, (worker / "worker.err.log").open("ab") as stderr:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                       env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
            process.stdin.write((code.group() + "\n").encode())
            process.stdin.close()
        record["worker_launcher_pid"] = process.pid
        record["worker_directory"] = str(worker)
        save()

        def ready_node():
            path = worker / "node-state.json"
            if not path.exists():
                return None
            state = json.loads(path.read_text(encoding="utf-8"))
            if not state.get("node_id"):
                return None
            node = api("GET", "/resources/nodes/" + state["node_id"])
            return node if node["online"] and node["approved"] and "image-classifier-v1" in node["inventory"]["runtime"]["trainers"] else None

        node = wait(ready_node)
        record["node_id"] = node["id"]
        save()
        print("云端已探测并准入本机CUDA Worker", flush=True)
        options = api("GET", prefix + "/job-options")
        model = next(item for item in options["models"] if item["trainer_id"] == "image-classifier-v1")
        dataset = next(item for item in options["datasets"] if item["task_type"] == "image_classification")
        job = api("POST", prefix + "/jobs", json={"name": "云端首次GPU训练 · TinyCNN", "kind": "train",
                  "project_id": record["project_id"], "model_version_id": model["id"], "dataset_version_id": dataset["id"],
                  "device_kind": "cuda", "min_memory_mb": 1024, "node_id": node["id"],
                  "config": {"epochs": 3, "batch_size": 8, "learning_rate": 0.003, "validation_ratio": 0.25, "seed": 42}})
        record["job_id"] = job["id"]
        save()
        job_path = prefix + "/jobs/" + job["id"]
        api("POST", job_path + "/submit", headers={"If-Match": f'"{job["revision"]}"'})

        def completed():
            current = api("GET", job_path)
            return current if current["status"] in {"succeeded", "failed", "stopped"} else None

        job = wait(completed, 300)
        record["job"] = job
        record["events"] = api("GET", job_path + "/events")
        save()
        assert job["status"] == "succeeded", job.get("error")
        assert job["result"]["device"] == "cuda"
        assert len([item for item in record["events"] if item["type"] == "metric"]) == 3
        artifact = client.get("/api/v1" + job_path + "/artifact")
        artifact.raise_for_status()
        assert hashlib.sha256(artifact.content).hexdigest() == artifact.headers["x-content-sha256"]
        target = root / "trained-model.zip"
        target.write_bytes(artifact.content)
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            record["artifact_files"] = archive.namelist()
        node = api("GET", "/resources/nodes/" + node["id"])
        record["gpu_released"] = all(not device["reserved_execution_id"] for device in node["devices"] if device["kind"] == "cuda")
        assert record["gpu_released"]
        record["success"] = True
        save()
        print(json.dumps({"success": True, "job_id": job["id"], "device": job["result"]["device"],
                          "result": job["result"], "gpu_released": True}, ensure_ascii=False), flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
