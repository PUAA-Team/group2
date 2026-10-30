"""通过正式业务服务与现有 Worker 执行公开数据实验，不伪造指标。"""
import argparse
import asyncio
from collections import Counter
import csv
import io
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from fastapi import UploadFile
from sqlalchemy import select
from model_platform.config import Settings
from model_platform.database import make_engine, make_session_factory, new_id
from model_platform.job_models import Job, Project, ServiceCall
from model_platform.job_schemas import CallInput, JobInput
from model_platform.models import Dataset, DatasetVersion, ModelAsset, ModelVersion, User
from model_platform.services.common import audit, commit
from model_platform.services.datasets import store_version
from model_platform.services.jobs import create_job, stop_job, submit_job
from model_platform.services.service_calls import create_call


def classification_scores(actual, predictions, labels):
    columns = labels + ["invalid"]
    matrix = [[0 for _ in columns] for _ in labels]
    for expected, predicted in zip(actual, predictions):
        matrix[labels.index(expected)][columns.index(predicted) if predicted in labels else -1] += 1
    f1 = [2 * matrix[i][i] / max(1, sum(matrix[i]) + sum(row[i] for row in matrix)) for i in range(len(labels))]
    return {"accuracy": sum(a == p for a, p in zip(actual, predictions)) / len(actual), "macro_f1": sum(f1) / len(f1),
            "labels": labels, "prediction_columns": columns, "confusion_matrix": matrix, "samples": len(actual), "invalid_outputs": sum(predicted not in labels for predicted in predictions)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("D:/model-training-demo/public-experiments-20261029"))
    parser.add_argument("--actor-id", required=True); parser.add_argument("--workspace-id", required=True)
    args = parser.parse_args(); root = args.root.resolve()
    if not root.is_relative_to(Path("D:/model-training-demo").resolve()):
        raise ValueError("实验运行目录须位于D盘")
    manifest = json.loads((root / "dataset-manifest.json").read_text(encoding="utf-8"))
    record_file = root / "experiment-run.json"
    record = json.loads(record_file.read_text(encoding="utf-8")) if record_file.exists() else {"workspace_id": args.workspace_id, "jobs": {}, "results": {}, "seed": 42}
    if record["workspace_id"] != args.workspace_id:
        raise ValueError("已有实验记录属于其他空间")
    settings = Settings(); engine = make_engine(settings.db_url); sessions = make_session_factory(engine)

    def persist():
        temporary = record_file.with_suffix(".pending.json")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"); temporary.replace(record_file)

    def wait(job_id, desired="succeeded", timeout=900):
        deadline = time.monotonic() + timeout; previous = None
        while time.monotonic() < deadline:
            with sessions() as db:
                job = db.get(Job, job_id)
                if job.status != previous:
                    print(f"{job.name}：{job.status}", flush=True); previous = job.status
                if job.status == desired:
                    return {"id": job.id, "result": job.result, "output_model_version_id": job.output_model_version_id, "config": job.config,
                            "model_version_id": job.model_version_id, "dataset_version_id": job.dataset_version_id, "status": job.status}
                if job.status in {"failed", "cancelled", "stopped"}:
                    raise RuntimeError(f"实验失败 {job.name}：{job.error}")
            time.sleep(1)
        raise RuntimeError("实验超时，请保留现场检查任务")

    def submit(key, payload):
        if key not in record["jobs"]:
            with sessions() as db:
                actor = db.get(User, args.actor_id)
                job = create_job(db, actor, args.workspace_id, JobInput(**payload, project_id=record["project_id"], device_kind="cuda"))
                job = submit_job(db, settings, actor, job, job.revision)
                record["jobs"][key] = job.id; persist()
        return record["jobs"][key]

    def asset_version(db, actor, name, task, trainer, source):
        model = db.scalar(select(ModelAsset).where(ModelAsset.workspace_id == args.workspace_id, ModelAsset.name == name))
        if not model:
            model = ModelAsset(id=new_id("mdl"), workspace_id=args.workspace_id, name=name, task_type=task, trainer_id=trainer, source_ref=source, description="公开数据实验")
            db.add(model); db.flush(); audit(db, actor, "models.create", model.id, args.workspace_id)
        version = db.scalar(select(ModelVersion).where(ModelVersion.model_id == model.id, ModelVersion.version == "base-v1"))
        if not version:
            version = ModelVersion(id=new_id("mvr"), model_id=model.id, version="base-v1", source_ref=source, created_by=actor.id)
            db.add(version)
        commit(db); return version.id

    async def data_version(db, actor, name, task, filename):
        dataset = db.scalar(select(Dataset).where(Dataset.workspace_id == args.workspace_id, Dataset.name == name))
        if not dataset:
            dataset = Dataset(id=new_id("dat"), workspace_id=args.workspace_id, name=name, task_type=task, description="公开数据固定划分，来源与划分摘要见实验记录")
            db.add(dataset); db.flush(); audit(db, actor, "datasets.create", dataset.id, args.workspace_id)
        version = db.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id).order_by(DatasetVersion.number))
        if not version:
            version = await store_version(db, settings, actor, dataset, UploadFile(io.BytesIO((root / "prepared" / filename).read_bytes()), filename=filename))
        return version.id

    try:
        with sessions() as db:
            actor = db.get(User, args.actor_id)
            if not actor or not actor.active:
                raise ValueError("操作账号不可用")
            project = db.scalar(select(Project).where(Project.workspace_id == args.workspace_id, Project.name == "公开数据实验"))
            if not project:
                project = Project(id=new_id("prj"), workspace_id=args.workspace_id, name="公开数据实验", created_by=actor.id)
                db.add(project); audit(db, actor, "projects.create", project.id, args.workspace_id); commit(db)
            record["project_id"] = project.id
            models = {"text": asset_version(db, actor, "SMS 字符分类器", "text_classification", "text-classifier-v1", "builtin://text-linear-v1"),
                      "image": asset_version(db, actor, "Fashion-MNIST TinyCNN", "image_classification", "image-classifier-v1", "builtin://tiny-cnn-v1"),
                      "qwen": asset_version(db, actor, "Qwen3-0.6B 短信分类", "llm_sft", "qwen-lora-v1", "Qwen/Qwen3-0.6B")}
            specs = [("sms_dev", "SMS 开发集", "text_classification", "sms-development.csv"), ("sms_test", "SMS 独立测试集", "text_classification", "sms-test.csv"),
                     ("fashion_dev", "Fashion-MNIST 开发集", "image_classification", "fashion-development.zip"), ("fashion_test", "Fashion-MNIST 独立测试集", "image_classification", "fashion-test.zip"),
                     ("qwen_dev", "SMS LoRA 开发集", "llm_sft", "qwen-sms-development.jsonl"), ("qwen_test", "SMS LoRA 独立测试集", "llm_sft", "qwen-sms-test.jsonl")]
            datasets = {key: asyncio.run(data_version(db, actor, name, task, filename)) for key, name, task, filename in specs}
            record["model_versions"], record["dataset_versions"] = models, datasets; persist()
        trials = [("sms_5", "SMS 字符分类 5epoch", "text", "sms_dev", "sms_test", {"epochs": 5, "batch_size": 32, "learning_rate": 0.01}),
                  ("sms_25", "SMS 字符分类 25epoch", "text", "sms_dev", "sms_test", {"epochs": 25, "batch_size": 32, "learning_rate": 0.03}),
                  ("fashion_3", "Fashion-MNIST 3epoch", "image", "fashion_dev", "fashion_test", {"epochs": 3, "batch_size": 32, "learning_rate": 0.003}),
                  ("fashion_10", "Fashion-MNIST 10epoch", "image", "fashion_dev", "fashion_test", {"epochs": 10, "batch_size": 32, "learning_rate": 0.003}),
                  ("qwen_1", "Qwen 短信 LoRA 512条", "qwen", "qwen_dev", "qwen_test", {"epochs": 1, "batch_size": 4, "learning_rate": 0.0002, "max_length": 192, "lora_rank": 4})]
        for key, name, model, development, testing, config in trials:
            trained = wait(submit(key, {"name": name, "model_version_id": models[model], "dataset_version_id": datasets[development], "config": config}))
            record["results"][key] = trained; persist()
            evaluated = wait(submit(key + "_test", {"name": name + " · 独立测试", "kind": "evaluate", "model_version_id": trained["output_model_version_id"], "dataset_version_id": datasets[testing]}))
            record["results"][key + "_test"] = evaluated; persist()
        testing = list(csv.DictReader((root / "prepared/sms-test.csv").open(encoding="utf-8")))
        majority = max(manifest["sms"]["development"], key=manifest["sms"]["development"].get)
        record["sms_majority_baseline"] = classification_scores([row["label"] for row in testing], [majority] * len(testing), ["ham", "spam"])
        record["fashion_majority_baseline"] = {"accuracy": 0.1, "macro_f1": 2 * 0.1 / 1.1 / 10, "samples": 2000}
        trained = record["results"]["qwen_1"]
        service_key = "qwen_service"
        # 已结束的服务不重用；新的调用批次另建服务执行，保留历史。
        if service_key in record["jobs"]:
            with sessions() as db:
                previous_service = db.get(Job, record["jobs"][service_key])
                if previous_service.status in {"stopped", "failed", "cancelled"}:
                    del record["jobs"][service_key]
        service_id = submit(service_key, {"name": "Qwen SMS 128条生成测试", "kind": "service", "model_version_id": trained["output_model_version_id"]})
        wait(service_id, "ready")
        generated = record.setdefault("qwen_predictions", {})
        held_out = json.loads((root / "prepared/sms-splits.json").read_text(encoding="utf-8"))["qwen_test"]
        try:
            for start in range(0, len(held_out), 16):
                pending = []
                for row in held_out[start:start + 16]:
                    if row["id"] in generated:
                        continue
                    with sessions() as db:
                        actor = db.get(User, args.actor_id); job = db.get(Job, service_id)
                        call = create_call(db, actor, job, CallInput(text="Classify the SMS as ham or spam. Reply with exactly ham or spam.\n" + row["text"], max_new_tokens=4))
                        pending.append((row, call["id"]))
                end = time.monotonic() + 180
                while pending:
                    remaining = []
                    for row, call_id in pending:
                        with sessions() as db:
                            call = db.get(ServiceCall, call_id)
                            if call.status == "pending":
                                remaining.append((row, call_id)); continue
                            if call.status != "succeeded":
                                raise RuntimeError("Qwen生成测试失败: " + str(call.result))
                            raw = call.result["text"]; label = raw.strip().lower().strip(" .\n\t`\"'")
                            generated[row["id"]] = {"actual": row["label"], "predicted": label if label in {"ham", "spam"} else "invalid", "output": raw, "call_id": call_id}
                    persist(); pending = remaining
                    if time.monotonic() > end:
                        raise RuntimeError("Qwen生成测试等待超时")
                    if pending:
                        time.sleep(0.5)
                print(f"Qwen生成测试：{min(start + 16, len(held_out))}/{len(held_out)}", flush=True)
            predictions = list(generated.values())
            record["qwen_generation_test"] = classification_scores([row["actual"] for row in predictions], [row["predicted"] for row in predictions], ["ham", "spam"])
            persist()
        finally:
            with sessions() as db:
                stop_job(db, db.get(User, args.actor_id), db.get(Job, service_id))
            wait(service_id, "stopped", 60)
        record["success"] = True; persist()
        print(json.dumps({"success": record.get("success"), "jobs": len(record["jobs"]), "qwen_generation": record.get("qwen_generation_test")}, ensure_ascii=False), flush=True)
    finally:
        persist(); engine.dispose()


if __name__ == "__main__":
    main()
