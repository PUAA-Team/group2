"""分两步更新待修复的本机Qwen服务，保存原配置与数据库备份。"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from sqlalchemy import select
from model_platform.compute_models import ComputeNode
from model_platform.compute_schemas import LocalWorkerInput
from model_platform.config import Settings
from model_platform.database import make_engine, make_session_factory
from model_platform.errors import Problem
from model_platform.job_models import Execution, Job, ServiceKey
from model_platform.job_schemas import JobInput
from model_platform.models import ModelVersion, User
from model_platform.permissions import workspace_access
from model_platform.services.common import audit, commit
from model_platform.services.compute import lock_node
from model_platform.services.inference_contracts import inference_suggestion
from model_platform.services.jobs import ACTIVE, create_job, stop_job, submit_job
from model_platform.services.local_worker import start_local_worker, stop_local_worker
from model_platform.services.process_state import process_alive

ROOT = Path("D:/model-training-demo/backend-runtime/qwen-contract-rollout-20261029")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["prepare", "resume"])
    parser.add_argument("--service-id"); args = parser.parse_args()
    settings = Settings(); engine = make_engine(settings.db_url); sessions = make_session_factory(engine)
    record_file = ROOT / "rollout.json"
    def save(record):
        record_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    def wait(callback, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = callback()
            if value:
                return value
            time.sleep(0.5)
        raise RuntimeError("服务切换等待超时，请保留现场")
    try:
        if args.action == "prepare":
            ROOT.mkdir(exist_ok=False)
            with sessions() as db:
                job = db.get(Job, args.service_id)
                if not job or job.kind != "service" or job.status != "ready" or job.snapshot.get("trainer_id") != "qwen-lora-v1":
                    raise ValueError("目标必须是正在运行的Qwen服务")
                actor = db.get(User, job.created_by)
                if not actor or not actor.active or not actor.is_admin:
                    raise ValueError("仅更新已确认管理员创建的本机服务")
                workspace_access(db, actor, job.workspace_id, "services.write")
                workspace_access(db, actor, job.workspace_id, "resources.manage")
                if db.scalar(select(ServiceKey.id).where(ServiceKey.job_id == job.id, ServiceKey.revoked_at.is_(None)).limit(1)):
                    raise ValueError("目标存在API KEY，请先确认调用方切换")
                execution = db.scalar(select(Execution).where(Execution.job_id == job.id))
                node = db.get(ComputeNode, execution.node_id)
                state = json.loads((settings.runtime_dir / "local-worker/node-state.json").read_text(encoding="utf-8"))
                if state.get("node_id") != node.id:
                    raise ValueError("该服务不在本机Worker，停止自动切换")
                others = db.scalars(select(Job).join(Execution, Execution.job_id == Job.id).where(Execution.node_id == node.id, Job.status.in_(ACTIVE), Job.id != job.id)).all()
                if others:
                    raise ValueError("该节点还有其他执行，请先确认维护范围")
                profile = inference_suggestion(db, settings, job.workspace_id, db.get(ModelVersion, job.model_version_id))
                if profile["mode"] != "label":
                    raise ValueError("训练数据没有明确短标签候选，请先确认部署指令")
                record = {"old_service_id": job.id, "actor_id": actor.id, "node_id": node.id, "node_was_enabled": node.enabled,
                          "original": {key: getattr(job, key) for key in JobInput.model_fields}, "inference": profile,
                          "original_worker_pid": state["pid"], "prepared_at": datetime.now().isoformat()}
                backup = ROOT / "platform-before.sqlite3"
                with sqlite3.connect(f"file:{(settings.runtime_dir / 'platform.sqlite3').as_posix()}?mode=ro", uri=True) as source, sqlite3.connect(backup) as target:
                    source.backup(target); assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                record["database_backup"] = str(backup); save(record)
                lock_node(db, node)
                if db.scalar(select(Job.id).join(Execution, Execution.job_id == Job.id).where(Execution.node_id == node.id, Job.status.in_(ACTIVE), Job.id != job.id).limit(1)):
                    raise ValueError("备份期间节点出现其他执行，停止自动切换")
                node.enabled = False; node.revision += 1
                audit(db, actor, "resources.contract.pause", node.id, node.workspace_id); commit(db)
                stop_job(db, actor, job)
            def service_stopped():
                with sessions() as db:
                    return db.get(Job, record["old_service_id"]).status == "stopped"
            wait(service_stopped)
            def stop_worker():
                with sessions() as db:
                    try:
                        stop_local_worker(db, settings, db.get(User, record["actor_id"])); return True
                    except Problem as error:
                        if error.status != 409:
                            raise
                        return False
            wait(stop_worker, 20)
            wait(lambda: not process_alive(record["original_worker_pid"]), 20)
            record["old_service_stopped"] = True; record["worker_stopped"] = True; save(record)
            print(json.dumps({"prepared": True, "old_service_id": record["old_service_id"], "backup": str(backup)}, ensure_ascii=False), flush=True)
        else:
            record = json.loads(record_file.read_text(encoding="utf-8"))
            if not record.get("worker_stopped"):
                raise ValueError("旧Worker尚未确认退出")
            with sessions() as db:
                actor = db.get(User, record["actor_id"])
                original = record["original"]
                job = db.get(Job, record["old_service_id"])
                receipt = start_local_worker(db, settings, actor, LocalWorkerInput(workspace_id=job.workspace_id, name="本机 RTX 4060", runtime_id="llm"))
                record["worker_start"] = receipt; save(record)
            def ready_node():
                with sessions() as db:
                    node = db.get(ComputeNode, record["node_id"])
                    return node.inventory.get("runtime", {}).get("inference_contract_version") == 1 and node.enabled
            wait(ready_node)
            if not record.get("new_service_id"):
                with sessions() as db:
                    actor = db.get(User, record["actor_id"])
                    config = {**original["config"], "inference": record["inference"]}
                    payload = JobInput(**{**original, "name": "Qwen 短信分类服务", "config": config})
                    new = create_job(db, actor, db.get(Job, record["old_service_id"]).workspace_id, payload)
                    submit_job(db, settings, actor, new, new.revision)
                    record["new_service_id"] = new.id; save(record)
            def ready_service():
                with sessions() as db:
                    job = db.get(Job, record["new_service_id"])
                    if job.status == "failed":
                        raise RuntimeError("分类服务启动失败：" + str(job.error))
                    return job.status == "ready"
            wait(ready_service)
            record["service_ready"] = True; save(record)
            print(json.dumps({"ready": True, "new_service_id": record["new_service_id"], "inference": record["inference"]}, ensure_ascii=False), flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
