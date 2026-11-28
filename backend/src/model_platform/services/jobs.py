import hashlib
import json

from sqlalchemy import func, select, update

from ..compute_models import ComputeNode
from ..database import new_id, utcnow
from ..errors import Problem
from ..job_models import Execution, Job, Project
from ..job_schemas import JobInput
from ..models import Dataset, DatasetVersion, ModelAsset, ModelVersion, User
from ..permissions import effective_policy, workspace_access, workspace_effective_quota
from .common import audit, commit, find_asset, revision_update, serialize
from .dataset_files import parse_samples
from .file_storage import read_verified, resolve_key
from .asset_lifecycle import ensure_active, lock_active
from .budgets import allocation_allowed
from .platform_settings import platform_config
from .resource_policies import configured_devices, device_fits, node_accepts_tasks, purpose_matches, runtime_fits

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
    ensure_active(model)
    if payload.config.inference is not None and (payload.kind != "service" or model.trainer_id != "qwen-lora-v1"):
        raise Problem(422, "INVALID_INFERENCE", "推理输出配置仅用于Qwen在线服务")
    if payload.project_id:
        lock_active(db, find_asset(db, Project, workspace_id, payload.project_id))
    if payload.node_id:
        find_asset(db, ComputeNode, workspace_id, payload.node_id)
    data = db.get(DatasetVersion, payload.dataset_version_id) if payload.dataset_version_id else None
    dataset = db.get(Dataset, data.dataset_id) if data else None
    ensure_active(dataset)
    if payload.kind != "service" and (not dataset or dataset.workspace_id != workspace_id or dataset.task_type != model.task_type or data.status != "available"):
        raise Problem(422, "INVALID_DATASET", "请选择已标注且任务匹配的数据版本")
    if payload.kind == "train" and data.provenance.get("partition") in {"validation", "test"}:
        raise Problem(422, "EVALUATION_PARTITION", "验证集和测试集不能用于训练")
    if payload.kind != "train" and (version.status != "available" or not version.source_ref.startswith(("artifact://", "upload://"))):
        raise Problem(422, "MODEL_NOT_READY", "评估和部署需要已训练或已导入的模型版本")
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


def job_devices(db, job, owner):
    return configured_devices(db, job.workspace_id, owner, device_kind=job.device_kind, node_id=job.node_id)


def submit_job(db, settings, actor, job, expected):
    if job.status != "draft":
        if job.revision == expected + 1 and job.status == "queued":
            return job
        raise Problem(409, "INVALID_STATE", "只有草稿可以提交")
    payload = JobInput(**{key: getattr(job, key) for key in JobInput.model_fields})
    model, version, data, dataset = inputs(db, job.workspace_id, payload)
    if job.node_id:
        devices = job_devices(db, job, db.get(User, job.created_by))
        if devices and not any(purpose_matches(purpose, job.kind) for _, _, purpose in devices):
            raise Problem(409, "DEVICE_PURPOSE_MISMATCH", "指定节点的设备用途与任务不匹配，请更换节点或自动选择")
    source = source_job(db, job.workspace_id, version)
    uploaded_model = version.source_ref.startswith("upload://") and version.status == "available" and version.storage_key
    if not source and not uploaded_model and version.source_ref != BUILTINS.get(model.trainer_id):
        raise Problem(422, "MODEL_SOURCE_UNSUPPORTED", "当前训练器支持预置基础模型、平台训练产物或受控导入权重，请登记兼容来源")
    if uploaded_model:
        read_verified(settings, version.storage_key, version.sha256, missing_message="导入的模型权重文件缺失")
    if data:
        path = resolve_key(settings, data.storage_key)
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
                "model_sha256": source.artifact_sha256 if source else (version.sha256 if uploaded_model else None), "config": job.config,
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


def update_job_priority(db, actor, workspace_id, job_id, priority, expected):
    job = find_asset(db, Job, workspace_id, job_id)
    workspace_access(db, actor, workspace_id, "resources.manage")
    if job.status != "queued":
        raise Problem(409, "INVALID_STATE", "只有排队中的任务可以调整优先级")
    old = job.priority
    revision_update(db, job, {"priority": priority}, expected)
    audit(db, actor, f"jobs.priority.{old}.{priority}", job.id, workspace_id)
    commit(db)
    return job


def personal_capacity_available(db, owner, device_kind, workspace_id=None):
    quota = workspace_effective_quota(db, owner, workspace_id) if workspace_id else effective_policy(db, owner)[1]
    own = select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE), Job.created_by == owner.id)
    return (db.scalar(own) < quota["concurrent_jobs"]
            and (device_kind != "cuda" or db.scalar(own.where(Job.device_kind == "cuda")) < quota["gpu_count"]))


def queue_reason(db, job, settings):
    if job.status != "queued":
        return None, None
    if job.project_id:
        project = db.get(Project, job.project_id)
        if project and project.archived:
            return "project_archived", "项目已归档，请先恢复项目"
    if job.node_id:
        node = db.get(ComputeNode, job.node_id)
        if node and node.inventory.get("runtime", {}).get("execution_contract_version", 0) < 1:
            return "worker_upgrade_required", "指定节点的 Worker 需要升级"
    if settings is None:
        return "waiting", "等待可用资源或执行额度"
    owner = db.get(User, job.created_by)
    if not owner or not owner.active:
        return "waiting", "等待可用资源或执行额度"
    try:
        workspace_access(db, owner, job.workspace_id, action_for(job.kind, True))
    except Problem:
        return "waiting", "等待可用资源或执行额度"
    configured = job_devices(db, job, owner)
    matching = [(node, device) for node, device, purpose in configured if purpose_matches(purpose, job.kind)]
    if configured and not matching:
        return "no_matching_purpose", "等待用途匹配的设备"
    now = utcnow()
    reason = "等待可见且规格匹配的设备"
    progress = 0
    slots_used = {}
    for node, device in matching:
        runtime = node.inventory.get("runtime", {})
        if not device_fits(job, device, runtime):
            continue
        if not node_accepts_tasks(node, settings, now):
            if progress < 1:
                progress, reason = 1, "等待节点上线或恢复接收任务"
            continue
        if runtime.get("execution_contract_version", 0) < 1 or not runtime_fits(job, runtime):
            if progress < 2:
                progress, reason = 2, "等待兼容的 Worker 运行环境"
            continue
        if device.reserved_execution_id is None:
            if node.id not in slots_used:
                slots_used[node.id] = db.scalar(select(func.count()).select_from(Execution).where(
                    Execution.node_id == node.id, Execution.finished_at.is_(None)))
            if slots_used[node.id] < node.slots:
                break
        if progress < 3:
            progress, reason = 3, "等待设备或节点槽位释放"
    else:
        return "no_available_device", reason
    active = select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE))
    if (db.scalar(active) >= platform_config(db).global_concurrent_jobs
            or not personal_capacity_available(db, owner, job.device_kind)
            or not allocation_allowed(db, owner, job.device_kind, lock=False)):
        return "quota_full", "等待执行额度"
    return "waiting", "等待可用资源或执行额度"


def job_view(db, job, settings=None):
    from .console import job_summary
    from .job_failures import failure_detail
    view = job_summary(db, job)
    execution = db.scalar(select(Execution).where(Execution.job_id == job.id))
    view["execution"] = serialize(execution) if execution else None
    view["queue_reason_code"], view["queue_reason"] = queue_reason(db, job, settings)
    if job.status == "failed":
        view["failure"] = failure_detail(db, job)
    return view
