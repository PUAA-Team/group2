import hashlib
import json

from sqlalchemy import select, update

from ..compute_models import ComputeNode
from ..database import new_id
from ..errors import Problem
from ..job_models import Execution, Job, Project
from ..job_schemas import JobInput
from ..models import Dataset, DatasetVersion, ModelAsset, ModelVersion
from ..permissions import workspace_access
from .common import audit, commit, find_asset, revision_update, serialize
from .dataset_files import controlled_path, parse_samples

ACTIVE = {"preparing", "running", "ready", "stopping"}
TERMINAL = {"succeeded", "failed", "stopped", "cancelled"}
QWEN_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
BUILTINS = {"text-classifier-v1": "builtin://text-linear-v1", "image-classifier-v1": "builtin://tiny-cnn-v1", "qwen-lora-v1": "Qwen/Qwen3-0.6B"}


def action_for(kind, write=False):
    return ("services" if kind == "service" else "training") + (".write" if write else ".read")


def get_job(db, actor, workspace_id, job_id, write=False):
    job = find_asset(db, Job, workspace_id, job_id)
    workspace_access(db, actor, workspace_id, action_for(job.kind, write))
    return job


def inputs(db, workspace_id, payload):
    version = db.get(ModelVersion, payload.model_version_id)
    model = db.get(ModelAsset, version.model_id) if version else None
    if not model or model.workspace_id != workspace_id:
        raise Problem(422, "INVALID_MODEL", "请选择本空间模型版本")
    if payload.config.inference is not None and (payload.kind != "service" or model.trainer_id != "qwen-lora-v1"):
        raise Problem(422, "INVALID_INFERENCE", "推理输出配置仅用于Qwen在线服务")
    if payload.project_id:
        find_asset(db, Project, workspace_id, payload.project_id)
    if payload.node_id:
        find_asset(db, ComputeNode, workspace_id, payload.node_id)
    data = db.get(DatasetVersion, payload.dataset_version_id) if payload.dataset_version_id else None
    dataset = db.get(Dataset, data.dataset_id) if data else None
    if payload.kind != "service" and (not dataset or dataset.workspace_id != workspace_id or dataset.task_type != model.task_type or data.status != "available"):
        raise Problem(422, "INVALID_DATASET", "请选择已标注且任务匹配的数据版本")
    if payload.kind == "train" and data.provenance.get("partition") in {"validation", "test"}:
        raise Problem(422, "EVALUATION_PARTITION", "验证集和测试集不能用于训练")
    if payload.kind != "train" and (version.status != "available" or not version.source_ref.startswith("artifact://")):
        raise Problem(422, "MODEL_NOT_READY", "评估和部署需要已训练的模型版本")
    if model.trainer_id == "qwen-lora-v1" and payload.device_kind != "cuda":
        raise Problem(422, "GPU_REQUIRED", "Qwen LoRA 需要 CUDA 设备")
    return model, version, data, dataset


def create_job(db, actor, workspace_id, payload):
    workspace_access(db, actor, workspace_id, action_for(payload.kind, True))
    inputs(db, workspace_id, payload)
    values = payload.model_dump(mode="json")
    job = Job(id=new_id("job"), workspace_id=workspace_id, created_by=actor.id, **values)
    db.add(job); audit(db, actor, "jobs.create", job.id, workspace_id); commit(db)
    return job


def source_job(db, workspace_id, version):
    if not version.source_ref.startswith("artifact://"):
        return None
    source = db.get(Job, version.source_ref.removeprefix("artifact://"))
    if not source or source.workspace_id != workspace_id or source.status != "succeeded" or not source.artifact_key or source.output_model_version_id != version.id:
        raise Problem(409, "MODEL_NOT_READY", "模型产物未就绪")
    return source


def submit_job(db, settings, actor, job, expected):
    if job.status != "draft":
        if job.revision == expected + 1 and job.status == "queued":
            return job
        raise Problem(409, "INVALID_STATE", "只有草稿可以提交")
    payload = JobInput(**{key: getattr(job, key) for key in JobInput.model_fields})
    model, version, data, dataset = inputs(db, job.workspace_id, payload)
    source = source_job(db, job.workspace_id, version)
    if not source and version.source_ref != BUILTINS.get(model.trainer_id):
        raise Problem(422, "MODEL_SOURCE_UNSUPPORTED", "当前训练器支持预置基础模型或平台训练产物，请登记兼容来源")
    if data:
        path = controlled_path(settings, data.storage_key)
        if not path.is_file():
            raise Problem(409, "DATA_NOT_READY", "数据版本文件缺失")
        rows, metadata = parse_samples(path.read_bytes(), dataset.task_type, data.filename, settings.max_samples)
        if metadata["sha256"] != data.sha256:
            raise Problem(409, "DATA_CHANGED", "数据文件校验失败")
        if model.task_type != "llm_sft":
            from collections import Counter
            labels = Counter(row["label"] for row in rows)
            if not 2 <= len(labels) <= 32 or min(labels.values()) < 2 or any(len(label) > 100 for label in labels):
                raise Problem(422, "INSUFFICIENT_SAMPLES", "分类数据需2～32类、每类至少两条，标签不超过100字")
        elif len(rows) < 2:
            raise Problem(422, "INSUFFICIENT_SAMPLES", "指令数据至少两条")
    snapshot = {"protocol_version": 1, "trainer_id": model.trainer_id, "task_type": model.task_type,
                "source_ref": version.source_ref, "model_version_id": version.id, "dataset_version_id": data.id if data else None,
                "dataset_sha256": data.sha256 if data else None, "dataset_format": data.format if data else None,
                "model_sha256": source.artifact_sha256 if source else None, "config": job.config,
                "qwen_revision": QWEN_REVISION if model.trainer_id == "qwen-lora-v1" else None}
    snapshot["sha256"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    revision_update(db, job, {"snapshot": snapshot, "status": "queued"}, expected)
    audit(db, actor, "jobs.submit", job.id, job.workspace_id); commit(db)
    return job


def stop_job(db, actor, job):
    # CAS 防止取消和 Worker 派发互相覆盖。
    desired = "cancelled" if job.status in {"draft", "queued"} else "stopping"
    if job.status in TERMINAL or job.status == "stopping":
        return job
    result = db.execute(update(Job).where(Job.id == job.id, Job.status == job.status).values(status=desired, revision=Job.revision + 1).execution_options(synchronize_session=False))
    if not result.rowcount:
        db.rollback(); raise Problem(409, "STATE_CHANGED", "任务状态已变化，请刷新重试")
    audit(db, actor, "jobs.stop", job.id, job.workspace_id); commit(db); db.refresh(job)
    return job


def job_view(db, job):
    from .console import job_summary
    view = job_summary(db, job)
    execution = db.scalar(select(Execution).where(Execution.job_id == job.id))
    view["execution"] = serialize(execution) if execution else None
    view["queue_reason"] = "等待可用资源或执行额度" if job.status == "queued" else None
    return view
