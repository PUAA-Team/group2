"""执行用户确认的本机演示配置，保留备份并复用正式业务服务。"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from sqlalchemy import select
from model_platform.config import Settings
from model_platform.database import make_engine, make_session_factory, new_id
from model_platform.job_models import Job
from model_platform.job_schemas import JobInput
from model_platform.models import Dataset, DatasetVersion, ModelAsset, ModelVersion, User, UserGroup
from model_platform.permissions import effective_policy
from model_platform.services.common import audit, commit, revision_update
from model_platform.services.jobs import create_job, submit_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    args = parser.parse_args(); settings = Settings(); root = settings.runtime_dir
    backup = root / "backups" / ("pre-demo-policy-" + time.strftime("%Y%m%d-%H%M%S") + ".sqlite3")
    with sqlite3.connect(f"file:{(root / 'platform.sqlite3').as_posix()}?mode=ro", uri=True) as source, sqlite3.connect(backup) as target:
        source.backup(target)
        assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    engine = make_engine(settings.db_url); sessions = make_session_factory(engine)
    report = {"backup": str(backup), "jobs": []}
    try:
        with sessions() as db:
            actor = db.get(User, args.actor_id)
            if not actor or not actor.is_admin or not actor.active:
                raise ValueError("只配置已确认的现有管理员")
            group = db.scalar(select(UserGroup).where(UserGroup.name == "本机开发组"))
            quota = {"gpu_count": 1, "concurrent_jobs": 2, "storage_gib": 10}
            if group and (group.quota != quota or group.deny_actions):
                raise ValueError("同名组配置不同，请人工核对")
            if actor.group_id and (not group or actor.group_id != group.id):
                raise ValueError("用户已被分配到其他组，请人工核对")
            if not group:
                group = UserGroup(id=new_id("grp"), name="本机开发组", quota=quota, allow_actions=[], deny_actions=[])
                db.add(group); db.flush(); audit(db, actor, "groups.create", group.id)
            revision_update(db, actor, {"group_id": group.id}, actor.revision)
            audit(db, actor, "users.update", actor.id); commit(db)
            report["quota"] = effective_policy(db, actor)[1]
            model = db.scalar(select(ModelVersion).join(ModelAsset).where(ModelAsset.workspace_id == args.workspace_id, ModelAsset.name == "文本线性分类器", ModelVersion.version == "base-v1"))
            data = db.scalar(select(DatasetVersion).join(Dataset).where(Dataset.workspace_id == args.workspace_id, Dataset.name == "反馈情感教学样本").order_by(DatasetVersion.number))
            if not model or not data:
                raise ValueError("缺少教学预置")
            def submit(payload):
                job = create_job(db, actor, args.workspace_id, JobInput(**payload))
                return submit_job(db, settings, actor, job, job.revision).id
            training_id = submit({"name": "文本分类首次训练", "model_version_id": model.id, "dataset_version_id": data.id, "config": {"epochs": 8, "batch_size": 4, "learning_rate": 0.03}})
            data_id = data.id
        def wait(job_id, desired="succeeded"):
            deadline = time.monotonic() + 150
            while time.monotonic() < deadline:
                with sessions() as poll:
                    job = poll.get(Job, job_id)
                    if job.status == desired:
                        return job
                    if job.status in {"failed", "cancelled", "stopped"}:
                        raise RuntimeError(f"演示任务未完成：{job.error}")
                time.sleep(1)
            raise RuntimeError("演示任务等待超时")
        trained = wait(training_id); report["jobs"].append(training_id)
        with sessions() as db:
            actor = db.get(User, args.actor_id)
            evaluation_id = submit({"name": "文本模型固定数据评估", "kind": "evaluate", "model_version_id": trained.output_model_version_id, "dataset_version_id": data_id})
        wait(evaluation_id); report["jobs"].append(evaluation_id)
        with sessions() as db:
            actor = db.get(User, args.actor_id)
            service_id = submit({"name": "文本分类演示服务", "kind": "service", "model_version_id": trained.output_model_version_id})
        wait(service_id, "ready"); report["jobs"].append(service_id)
        report["success"] = True
        print(json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        (root / "local-demo.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        engine.dispose()


if __name__ == "__main__":
    main()
