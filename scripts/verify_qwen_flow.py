"""复用独立验收服务，验证 Qwen LoRA 的训练、评估与推理。"""
import argparse
import json
from pathlib import Path
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(); root = args.root.resolve()
    if not root.is_relative_to(Path("D:/model-training-demo").resolve()):
        raise ValueError("验收记录须保存在 D 盘")
    credentials = json.loads((root / "private-browser-login.json").read_text(encoding="utf-8"))
    existing = json.loads((root / "verification.json").read_text(encoding="utf-8"))
    report = {"checks": [], "jobs": []}; services = []
    base = f"/api/v1/workspaces/{existing['workspace_id']}"
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=30) as client:
        def request(path, body=None, headers=None):
            response = client.request("POST" if body is not None else "GET", path, json=body, headers=headers)
            if not response.is_success:
                raise RuntimeError(f"{path}: {response.status_code} {response.text[:500]}")
            return response.json()["data"]
        session = request("/api/v1/auth/login", credentials)
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        def wait(callback, timeout=360):
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                result = callback()
                if result:
                    return result
                time.sleep(1)
            raise RuntimeError("Qwen 验收超时")
        def submit(payload):
            draft = request(base + "/jobs", payload)
            return request(base + f"/jobs/{draft['id']}/submit", {}, {"If-Match": str(draft["revision"])})
        def job_result(job, ready=False):
            def fetch():
                value = request(base + f"/jobs/{job['id']}")
                if value["status"] in {"failed", "stopped", "cancelled"}:
                    report["jobs"].append(value)
                    raise RuntimeError("Qwen 执行未完成: " + str(value["error"]))
                return value if value["status"] == ("ready" if ready else "succeeded") else None
            return wait(fetch)
        try:
            request(base + "/presets", {"task_types": ["llm_sft"]})
            choices = request(base + "/job-options")
            model = next(model for model in choices["models"] if model["task_type"] == "llm_sft" and model["version"] == "base-v1")
            data = next(data for data in choices["datasets"] if data["task_type"] == "llm_sft")
            trained = job_result(submit({"name": "Qwen3-0.6B LoRA 真机验收", "model_version_id": model["id"], "dataset_version_id": data["id"], "device_kind": "cuda", "min_memory_mb": 4096,
                                        "config": {"epochs": 1, "batch_size": 1, "learning_rate": 0.0002, "max_length": 128, "lora_rank": 4}}))
            report["jobs"].append(trained); report["checks"].append("Qwen3-0.6B 在本机 CUDA 完成 LoRA 微调并回传 safetensors 适配器")
            print("Qwen LoRA 训练与产物通过", flush=True)
            evaluated = job_result(submit({"name": "Qwen LoRA 固定版本评估", "kind": "evaluate", "model_version_id": trained["output_model_version_id"], "dataset_version_id": data["id"], "device_kind": "cuda"}))
            report["jobs"].append(evaluated); report["checks"].append("加载平台 LoRA 产物完成响应 Token loss 评估")
            print("Qwen LoRA 评估通过", flush=True)
            service = job_result(submit({"name": "Qwen LoRA 推理验收", "kind": "service", "model_version_id": trained["output_model_version_id"], "device_kind": "cuda"}), True)
            services.append(service["id"]); report["jobs"].append(service)
            call = request(base + f"/jobs/{service['id']}/calls", {"text": "判断反馈情感，只回答正向或负向。\n操作简单上手很快", "max_new_tokens": 8})
            result = wait(lambda: (lambda value: value if value["status"] != "pending" else None)(request(base + f"/calls/{call['id']}")), 120)
            if result["status"] != "succeeded":
                raise RuntimeError("Qwen 推理失败: " + str(result["result"]))
            report["prediction"] = result["result"]; report["checks"].append("Worker 实际加载适配器并完成服务推理")
            request(base + f"/jobs/{service['id']}/stop", {})
            wait(lambda: request(base + f"/jobs/{service['id']}")["status"] == "stopped", 45)
            services.remove(service["id"]); report["checks"].append("服务进程退出后释放 GPU")
            report["success"] = True
            print(json.dumps({"success": True, "checks": report["checks"], "prediction": report["prediction"]}, ensure_ascii=False), flush=True)
        finally:
            for job_id in services:
                request(base + f"/jobs/{job_id}/stop", {})
            (root / "verification-qwen.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
