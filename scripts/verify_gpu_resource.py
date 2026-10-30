"""在独立 D 盘库启动控制端和真实本机 Worker，验证资源接入。"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import httpx

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.drive.upper() != "D:" or not root.is_relative_to(Path("D:/model-training-demo")):
        raise ValueError("验收目录必须在 D 盘项目下")
    root.mkdir(parents=True, exist_ok=False)
    (root / "temp").mkdir()
    env = {**os.environ, "MT_RUNTIME_DIR": str(root), "MT_ALLOW_BROWSER_SETUP": "1", "MT_ENABLE_LOCAL_WORKER": "1",
           "MT_LOCAL_CONTROLLER_URL": "http://127.0.0.1:8001", "MT_ALLOWED_ORIGINS": "http://127.0.0.1:8001",
           "PYTHONPATH": str(REPO / "backend/src"), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
           "TEMP": str(root / "temp"), "TMP": str(root / "temp")}
    subprocess.run([sys.executable, "-B", "-m", "model_platform.cli", "migrate"], env=env, check=True)
    report = {"checks": []}
    stdout = (root / "server.out.log").open("wb"); stderr = (root / "server.err.log").open("wb")
    server = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "model_platform.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "8001", "--no-access-log"], env=env,
                              stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    client = httpx.Client(base_url="http://127.0.0.1:8001", timeout=20)
    def request(path, body=None):
        response = client.post(path, json=body) if body is not None else client.get(path)
        if response.status_code >= 400:
            raise RuntimeError(f"请求未完成：{path}, HTTP {response.status_code}")
        return response.json()["data"]
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                if client.get("/readyz").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("验收服务未就绪")
            time.sleep(0.2)
        password = secrets.token_urlsafe(24)
        request("/api/v1/setup", {"account": "gpu-review", "display_name": "GPU 验收", "password": password})
        logged = request("/api/v1/auth/login", {"account": "gpu-review", "password": password})
        client.headers["X-CSRF-Token"] = logged["csrf_token"]
        space = request("/api/v1/workspaces", {"name": "GPU 资源验收"})
        start = request("/api/v1/admin/local-worker", {"workspace_id": space["id"], "name": "本机 RTX 4060 验收", "runtime_id": "llm"})
        report["start"] = start
        deadline = time.monotonic() + 90
        while True:
            nodes = request("/api/v1/admin/nodes")
            if nodes and nodes[0]["online"]:
                node = nodes[0]; break
            if time.monotonic() > deadline:
                raise RuntimeError("Worker 未在时限内完成注册")
            time.sleep(1)
        assert node["approved"] and node["inventory"]["runtime"]["cuda_available"]
        assert any(device["kind"] == "cuda" and "4060" in device["name"] for device in node["devices"])
        report["node"] = node
        report["checks"].append("本机独立 Worker 注册、GPU 和 CUDA 真实探测")
        old_seen = node["last_seen_at"]
        time.sleep(4)
        latest = request(f"/api/v1/resources/nodes/{node['id']}")
        assert latest["last_seen_at"] > old_seen
        report["checks"].append("连续心跳时间推进")
        probe = request(f"/api/v1/resources/nodes/{node['id']}/probe", {})
        deadline = time.monotonic() + 90
        while True:
            latest = request(f"/api/v1/resources/nodes/{node['id']}")
            if latest["probe_request_id"] is None and latest["last_inventory_at"] > node["last_inventory_at"]:
                break
            if time.monotonic() > deadline:
                raise RuntimeError("主动探测未回传")
            time.sleep(1)
        report["checks"].append("控制消息驱动重新探测并确认")
        report["probe"] = probe
        stop = request("/api/v1/admin/local-worker/stop", {})
        deadline = time.monotonic() + 10
        while not (root / "local-worker/stopped.json").exists():
            if time.monotonic() > deadline:
                raise RuntimeError("Worker 未确认停止")
            time.sleep(0.2)
        report["checks"].append("本机 Worker 有停止回执")
        report["stop"] = stop
        report["success"] = True
        print(json.dumps({"success": True, "checks": len(report["checks"]), "gpu": [device["name"] for device in node["devices"] if device["kind"] == "cuda"]}, ensure_ascii=False), flush=True)
    finally:
        try:
            if "X-CSRF-Token" in client.headers:
                request("/api/v1/admin/local-worker/stop", {})
        finally:
            client.close(); server.terminate(); server.wait(timeout=10); stdout.close(); stderr.close()
            (root / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
