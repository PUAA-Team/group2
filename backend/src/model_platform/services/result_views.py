"""评估对比与服务调用元数据；不在汇总接口返回输入正文。"""
import math

from sqlalchemy import func, select

from ..errors import Problem
from ..job_models import Job, ServiceCall
from ..models import Dataset, DatasetVersion, ModelAsset, ModelVersion, User
from ..permissions import workspace_access
from .common import serialize
from .jobs import get_job

METRICS = ("accuracy", "macro_f1", "loss", "validation_loss", "perplexity", "samples", "response_tokens")


def compare_evaluations(db, actor, workspace_id, identifiers):
    workspace_access(db, actor, workspace_id, "training.read")
    if not 2 <= len(identifiers) <= 6 or len(set(identifiers)) != len(identifiers):
        raise Problem(422, "INVALID_SELECTION", "请选择2～6个不同的已完成评估")
    jobs = [get_job(db, actor, workspace_id, identifier) for identifier in identifiers]
    if any(job.kind != "evaluate" or job.status != "succeeded" for job in jobs):
        raise Problem(409, "EVALUATION_NOT_READY", "对比仅支持已完成的评估任务")
    first = jobs[0]
    task = first.snapshot.get("task_type")
    if not task or any(job.dataset_version_id != first.dataset_version_id or
        job.snapshot.get("task_type") != task or job.config != first.config or
        job.snapshot.get("dataset_sha256") != first.snapshot.get("dataset_sha256") for job in jobs):
        raise Problem(409, "INCOMPARABLE_EVALUATIONS", "请选择同一数据版本、任务类型和评估配置的结果")
    version = db.get(DatasetVersion, first.dataset_version_id)
    dataset = db.get(Dataset, version.dataset_id) if version else None
    if not dataset or dataset.workspace_id != workspace_id or version.sha256 != first.snapshot.get("dataset_sha256"):
        raise Problem(409, "INVALID_SOURCE", "评估数据来源无法核对")
    items = []
    for job in jobs:
        model_version = db.get(ModelVersion, job.model_version_id)
        model = db.get(ModelAsset, model_version.model_id)
        metrics = {key: value for key in METRICS if type(value := job.result.get(key)) in (float, int) and math.isfinite(value)}
        items.append({"id": job.id, "name": job.name, "model_id": model.id, "model_name": model.name,
            "model_version": model_version.version, "created_at": serialize(job)["created_at"], "metrics": metrics,
            "labels": job.result.get("labels"), "confusion_matrix": job.result.get("confusion_matrix"),
            "errors_available": "error_samples" in job.result})
    return {"task_type": task, "dataset": {"id": dataset.id, "name": dataset.name,
        "version_id": version.id, "number": version.number, "sha256": version.sha256},
        "config": first.config, "items": items}


def service_job(db, actor, workspace_id, job_id):
    job = get_job(db, actor, workspace_id, job_id)
    if job.kind != "service":
        raise Problem(422, "INVALID_SERVICE", "此任务不是在线服务")
    return job


def call_history(db, actor, workspace_id, job_id, page, page_size, status):
    service_job(db, actor, workspace_id, job_id)
    query = select(ServiceCall).where(ServiceCall.job_id == job_id)
    if status:
        query = query.where(ServiceCall.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(ServiceCall.created_at.desc(), ServiceCall.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    users = {user.id: user.display_name for user in db.scalars(select(User).where(User.id.in_({row.created_by for row in rows})))}
    return [{"id": row.id, "status": row.status, "created_at": serialize(row)["created_at"],
             "completed_at": serialize(row)["completed_at"], "elapsed_ms": row.elapsed_ms,
             "actor_name": users.get(row.created_by, "未知成员")} for row in rows], {
                 "page": page, "page_size": page_size, "total": total}


def call_statistics(db, actor, workspace_id, job_id):
    service_job(db, actor, workspace_id, job_id)
    counts = dict(db.execute(select(ServiceCall.status, func.count()).where(
        ServiceCall.job_id == job_id).group_by(ServiceCall.status)).all())
    measured, mean, low, high = db.execute(select(func.count(ServiceCall.elapsed_ms),
        func.avg(ServiceCall.elapsed_ms), func.min(ServiceCall.elapsed_ms), func.max(ServiceCall.elapsed_ms))
        .where(ServiceCall.job_id == job_id)).one()
    return {"total": sum(counts.values()), "pending": counts.get("pending", 0),
            "succeeded": counts.get("succeeded", 0), "failed": counts.get("failed", 0),
            "measured_calls": measured, "mean_ms": round(mean) if mean is not None else None,
            "min_ms": low, "max_ms": high}
