"""在 D 盘独立库执行真实 Worker 训练、评估、服务和密钥验收。"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--qwen", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--image-device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_relative_to(Path("D:/model-training-demo").resolve()):
        raise ValueError("验收运行文件必须在 D 盘项目目录")
    root.mkdir(parents=True, exist_ok=False); (root / "temp").mkdir()
    repo = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(MT_RUNTIME_DIR=str(root), MT_ALLOW_BROWSER_SETUP="1", MT_ENABLE_LOCAL_WORKER="1", MT_LOCAL_CONTROLLER_URL="http://127.0.0.1:8001",
                       MT_ALLOWED_ORIGINS="http://127.0.0.1:8001", PYTHONPATH=str(repo / "backend/src"), PYTHONDONTWRITEBYTECODE="1",
                       PYTHONIOENCODING="utf-8", TEMP=str(root / "temp"), TMP=str(root / "temp"))
    subprocess.run([sys.executable, "-B", "-m", "model_platform.cli", "migrate"], cwd=repo, env=environment, check=True)
    stdout = (root / "server.out.log").open("w", encoding="utf-8"); stderr = (root / "server.err.log").open("w", encoding="utf-8")
    server = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "model_platform.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "8001", "--no-access-log"],
                              cwd=repo, env=environment, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    (root / "server-process.json").write_text(json.dumps({"pid": server.pid, "port": 8001}), encoding="utf-8")
    client = httpx.Client(base_url="http://127.0.0.1:8001", timeout=30)
    report = {"checks": [], "jobs": [], "qwen_requested": args.qwen}
    services = []

    def request(path, body=None, *, method=None, headers=None):
        result = client.request(method or ("POST" if body is not None else "GET"), path, json=body, headers=headers)
        if not result.is_success:
            raise RuntimeError(f"{path}: {result.status_code} {result.text[:700]}")
        return result.json()["data"]

    def until(callback, timeout=120):
        deadline = time.monotonic() + timeout
        while True:
            result = callback()
            if result:
                return result
            if time.monotonic() >= deadline:
                raise RuntimeError("验收等待超时")
            time.sleep(1)

    base = None
    def queued(payload):
        job = request(base + "/jobs", payload)
        return request(base + f"/jobs/{job['id']}/submit", {}, headers={"If-Match": str(job["revision"])})

    def wait_job(job, timeout=180, ready=False):
        def state():
            latest = request(base + f"/jobs/{job['id']}")
            if latest["status"] in {"failed", "stopped", "cancelled"}:
                raise RuntimeError(f"任务失败 {latest['name']}: {latest['error']}")
            return latest if latest["status"] == ("ready" if ready else "succeeded") else None
        return until(state, timeout)

    try:
        def ready():
            try:
                return client.get("/readyz").status_code == 200
            except httpx.HTTPError:
                return False
        until(ready, 30)
        password = secrets.token_urlsafe(24)
        request("/api/v1/setup", {"account": "workflow-review", "display_name": "闭环验收", "password": password})
        session = request("/api/v1/auth/login", {"account": "workflow-review", "password": password})
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        if args.keep:
            fd = os.open(root / "private-browser-login.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"account": "workflow-review", "password": password}, stream)
        workspace = request("/api/v1/workspaces", {"name": "真实闭环验收"})
        base = f"/api/v1/workspaces/{workspace['id']}"
        actions = ["models.read", "models.write", "datasets.read", "datasets.write", "training.read", "training.write", "services.read", "services.write", "services.invoke", "resources.read", "resources.manage"]
        group = request("/api/v1/admin/groups", {"name": "验收资源额度", "allow_actions": actions, "quota": {"gpu_count": 1, "concurrent_jobs": 2, "storage_gib": 10}})
        request(f"/api/v1/admin/users/{session['user']['id']}", {"group_id": group["id"]}, method="PATCH", headers={"If-Match": str(session["user"]["revision"])})
        kinds = ["text_classification", "image_classification"] + (["llm_sft"] if args.qwen else [])
        request(base + "/presets", {"task_types": kinds})
        choices = request(base + "/job-options")
        request("/api/v1/admin/local-worker", {"workspace_id": workspace["id"], "name": "本机训练节点", "runtime_id": "llm"})
        until(lambda: next((node for node in request("/api/v1/admin/nodes") if len(node["inventory"].get("runtime", {}).get("trainers", [])) == 3), None), 100)
        report["checks"].append("三类真实训练器通过运行时探测")
        for kind in kinds:
            model = next(item for item in choices["models"] if item["task_type"] == kind)
            dataset = next(item for item in choices["datasets"] if item["task_type"] == kind)
            device = "cuda" if kind == "llm_sft" else args.image_device if kind == "image_classification" else "cpu"
            trained = wait_job(queued({"name": TASK_NAMES[kind] + "训练", "model_version_id": model["id"], "dataset_version_id": dataset["id"], "device_kind": device,
                                       "config": {"epochs": 1 if kind == "llm_sft" else 6, "batch_size": 1 if kind == "llm_sft" else 8, "learning_rate": 0.0002 if kind == "llm_sft" else 0.01}}), 360)
            report["jobs"].append(trained); report["checks"].append(TASK_NAMES[kind] + "真实训练与产物入库")
            evaluated = wait_job(queued({"name": TASK_NAMES[kind] + "评估", "kind": "evaluate", "model_version_id": trained["output_model_version_id"], "dataset_version_id": dataset["id"], "device_kind": device}), 240)
            report["jobs"].append(evaluated); report["checks"].append(TASK_NAMES[kind] + "固定版本真实评估")
            service = wait_job(queued({"name": TASK_NAMES[kind] + "在线服务", "kind": "service", "model_version_id": trained["output_model_version_id"], "device_kind": device}), 240, True)
            services.append(service["id"]); report["jobs"].append(service)
            if kind == "image_classification":
                import base64
                import io
                from PIL import Image, ImageDraw
                image = Image.new("RGB", (32, 32), "white"); ImageDraw.Draw(image).ellipse((4, 4, 28, 28), fill="black")
                raw = io.BytesIO(); image.save(raw, format="PNG"); payload = {"image_base64": base64.b64encode(raw.getvalue()).decode()}
            else:
                payload = {"text": "判断反馈情感，只回答正向或负向。\n操作简单上手很快" if kind == "llm_sft" else "操作简单上手很快", "max_new_tokens": 8}
            call = request(base + f"/jobs/{service['id']}/calls", payload)
            completed = until(lambda: (lambda value: value if value["status"] != "pending" else None)(request(base + f"/calls/{call['id']}")), 90)
            assert completed["status"] == "succeeded", completed
            report["checks"].append(TASK_NAMES[kind] + "模型加载与真实推理")
            report.setdefault("predictions", []).append({"kind": kind, "result": completed["result"]})
            key = request(base + "/service-keys", {"name": TASK_NAMES[kind] + "验收密钥", "job_id": service["id"]})
            with httpx.Client(base_url=str(client.base_url), headers={"Authorization": "Bearer " + key["key"]}, timeout=15) as external:
                response = external.post(f"/api/inference/v1/services/{service['id']}/predict", json=payload)
                assert response.status_code == 202, response.text
                external_id = response.json()["data"]["id"]
                external_call = until(lambda: (lambda value: value if value["status"] != "pending" else None)(external.get(f"/api/inference/v1/services/{service['id']}/calls/{external_id}").json()["data"]), 90)
                assert external_call["status"] == "succeeded"
                request(base + f"/service-keys/{key['id']}/revoke", {})
                assert external.post(f"/api/inference/v1/services/{service['id']}/predict", json=payload).status_code == 401
            report["checks"].append(TASK_NAMES[kind] + "API KEY 调用与撤销")
            request(base + f"/jobs/{service['id']}/stop", {})
            until(lambda: request(base + f"/jobs/{service['id']}")["status"] == "stopped", 30)
            services.remove(service["id"])
        report["success"] = True
        report["workspace_id"] = workspace["id"]
        print(json.dumps({"success": True, "checks": report["checks"], "jobs": len(report["jobs"])}, ensure_ascii=False), flush=True)
    finally:
        (root / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.keep:
            try:
                if base:
                    for service_id in services:
                        request(base + f"/jobs/{service_id}/stop", {})
                    for _ in range(20):
                        try:
                            request("/api/v1/admin/local-worker/stop", {}); break
                        except RuntimeError:
                            time.sleep(1)
                    stopped = root / "local-worker/stopped.json"
                    for _ in range(20):
                        if stopped.exists(): break
                        time.sleep(0.5)
            finally:
                client.close(); server.terminate(); server.wait(timeout=15); stdout.close(); stderr.close()


TASK_NAMES = {"text_classification": "文本分类", "image_classification": "图像分类", "llm_sft": "Qwen LoRA"}

if __name__ == "__main__":
    main()
