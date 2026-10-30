"""在独立示例空间验收真实PostgreSQL数据流程，不改变旧资产或训练。"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

import httpx

ROOT = Path("D:/model-training-demo/stage13-20261029")
LOGIN = Path("D:/model-training-demo/server-deploy-prep-20261029/private-admin-login.json")
URL = "https://47.93.115.188:5488"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy", help="仅本进程使用现有回环HTTP代理")
    args = parser.parse_args()
    if args.proxy:
        proxy = urlsplit(args.proxy)
        assert proxy.scheme == "http" and proxy.hostname in {"127.0.0.1", "localhost", "::1"} and proxy.port and not proxy.username and not proxy.password
    state_path = ROOT / "cloud-data-work.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    private = json.loads(LOGIN.read_text())
    with httpx.Client(base_url=URL + "/api/v1", timeout=30, trust_env=False, proxy=args.proxy) as client:
        def api(method, path, **kwargs):
            result = client.request(method, path, **kwargs)
            if not result.is_success:
                raise RuntimeError(f"云端验收失败：{method} {path}，HTTP {result.status_code}")
            return result.json()["data"]

        session = api("POST", "/auth/login", json={"account": private["account"], "password": private["password"]})
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        if not state.get("workspace_id"):
            state["workspace_id"] = api("POST", "/workspaces", json={"name": "数据工作流示例"})["id"]
            state_path.write_text(json.dumps(state))
        base = "/workspaces/" + state["workspace_id"]

        def asset(key, name, task, filename, content):
            if key not in state:
                dataset = api("POST", base + "/datasets", json={"name": name, "task_type": task})
                state[key] = {"dataset": dataset["id"]}
                state_path.write_text(json.dumps(state))
            item = state[key]
            if "version" not in item:
                version = api("POST", base + "/datasets/" + item["dataset"] + "/versions", files={"file": (filename, content)})
                assert version["sha256"] == hashlib.sha256(content).hexdigest()
                item["version"], item["sample_count"] = version["id"], version["sample_count"]
                state_path.write_text(json.dumps(state))
            return item

        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["text", "label"])
        writer.writerows([[" 这个工具很好用 ", "正向"], ["这个工具很好用", "正向"]] + [[text, label] for text, label in [
            ("配置步骤清楚", "正向"), ("训练结果满意", "正向"), ("页面操作方便", "正向"), ("任务启动顺利", "正向"), ("希望增加更多示例", "正向"),
            ("上传等待太久", "负向"), ("日志看不明白", "负向"), ("参数配置困难", "负向"), ("操作经常报错", "负向"), ("缺少错误提示", "负向")]])
        text = asset("text", "反馈分类·流程示例", "text_classification", "feedback.csv", output.getvalue().encode("utf-8-sig"))
        template = client.get("/dataset-templates/image-classification")
        template.raise_for_status()
        images = asset("images", "形状分类·增强示例", "image_classification", "images.zip", template.content)
        if not state.get("batch_id"):
            batch = api("POST", base + "/annotation-batches", json={"name": "反馈分类人工复核", "version_id": text["version"], "labels": ["正向", "负向"], "limit": 2})
            state["batch_id"] = batch["id"]
            state_path.write_text(json.dumps(state))
        batch_path = base + "/annotation-batches/" + state["batch_id"]
        batch = api("GET", batch_path)
        if batch["status"] != "published":
            for sample in batch["samples"]:
                result = sample["result"]
                if not result or result["state"] not in {"approved", "submitted"}:
                    api("POST", batch_path + "/results/" + str(sample["index"]), json={"value": "正向", "revision": result["revision"] if result else 0, "submit": True})
            batch = api("GET", batch_path)
            indices = [sample["index"] for sample in batch["samples"] if sample["result"]["state"] == "submitted"]
            if indices:
                api("POST", batch_path + "/review", json={"indices": indices, "decision": "approved", "revision": batch["revision"]})
            api("POST", batch_path + "/publish")
        batch = api("GET", batch_path)
        assert batch["status"] == "published" and batch["counts"]["approved"] == 2

        def operation(key, name, version, kind, options, publish):
            if key not in state:
                item = api("POST", base + "/data-operations", json={"name": name, "version_id": version, "kind": kind, "options": options})
                state[key] = item["id"]
                state_path.write_text(json.dumps(state))
            path = base + "/data-operations/" + state[key]
            for _ in range(120):
                item = api("GET", path)
                if item["status"] not in {"queued", "running"}:
                    break
                time.sleep(0.5)
            assert item["status"] in {"review", "published"}, item["status"]
            preview = api("GET", path + "/preview")
            assert preview["total"] > 0 and "storage_key" not in str(item)
            if publish:
                ids = api("POST", path + "/publish")["output_version_ids"]
                assert api("POST", path + "/publish")["output_version_ids"] == ids
                item = api("GET", path)
            return item

        clean = operation("clean_id", "反馈分类清洗", text["version"], "clean", {}, True)
        assert clean["candidates"][0]["sample_count"] == 11
        split = operation("split_id", "反馈分类分层划分", clean["output_version_ids"][0], "split", {"seed": 42}, True)
        assert len(split["output_version_ids"]) == 3
        augmentation = operation("augmentation_id", "形状图像水平翻转", images["version"], "augment", {"methods": ["flip"], "seed": 42}, False)
        assert augmentation["candidates"][0]["sample_count"] == images["sample_count"] * 2
        for index in (0, 1):
            image = client.get(base + f"/data-operations/{augmentation['id']}/images/{index}")
            assert image.is_success and image.headers["content-type"] == "image/png"
        original = client.get(base + f"/dataset-versions/{text['version']}/download")
        assert hashlib.sha256(original.content).hexdigest() == hashlib.sha256(output.getvalue().encode("utf-8-sig")).hexdigest()
        report = {"url": URL, "workspace_id": state["workspace_id"], "workspace_name": "数据工作流示例", "annotation_id": state["batch_id"],
            "text": text, "images": images, "clean_id": clean["id"], "split_id": split["id"], "augmentation_id": augmentation["id"],
            "annotation_published": True, "clean_counts": [12, 11], "split_counts": [item["sample_count"] for item in split["candidates"]],
            "augmentation_counts": [images["sample_count"], augmentation["candidates"][0]["sample_count"]], "source_preserved": True,
            "real_postgresql_workflow": True, "gpu_used": False, "training_metrics_created": False}
        (ROOT / "cloud-data-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key not in {"text", "images"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
