"""完整控制台的只读汇总，所有查询保持空间与读取权限边界。"""
from sqlalchemy import func, select

from ..errors import Problem
from ..job_models import Job, Project
from ..models import AuditEvent, Dataset, DatasetVersion, Membership, ModelAsset, ModelVersion, User, Workspace
from ..permissions import effective_policy, workspace_access
from .common import page_data, search_query, serialize


def overview(db, actor, workspace_id):
    space = db.get(Workspace, workspace_id)
    if space is None or (not actor.is_admin and not db.get(Membership, (workspace_id, actor.id))):
        raise Problem(404, "NOT_FOUND", "工作空间不存在")
    actions, _ = effective_policy(db, actor)
    counts = {key: None for key in ("projects", "queued", "active", "succeeded", "datasets", "models")}
    recent, activity = [], []
    if "training.read" in actions:
        counts["projects"] = db.scalar(select(func.count()).select_from(Project).where(Project.workspace_id == workspace_id))
        status_counts = dict(db.execute(select(Job.status, func.count()).where(Job.workspace_id == workspace_id, Job.kind == "train").group_by(Job.status)).all())
        counts.update(queued=status_counts.get("queued", 0), active=sum(status_counts.get(key, 0) for key in ("preparing", "running", "stopping")), succeeded=status_counts.get("succeeded", 0))
        recent = [job_summary(db, item) for item in db.scalars(select(Job).where(Job.workspace_id == workspace_id, Job.kind == "train").order_by(Job.created_at.desc(), Job.id.desc()).limit(6))]
    if "datasets.read" in actions:
        counts["datasets"] = db.scalar(select(func.count(func.distinct(Dataset.id))).join(DatasetVersion, DatasetVersion.dataset_id == Dataset.id).where(Dataset.workspace_id == workspace_id, DatasetVersion.status == "available"))
    if "models.read" in actions:
        counts["models"] = db.scalar(select(func.count()).select_from(ModelAsset).where(ModelAsset.workspace_id == workspace_id))
    if "audit.read" in actions:
        for event, name in db.execute(select(AuditEvent, User.display_name).join(User, User.id == AuditEvent.actor_id).where(AuditEvent.workspace_id == workspace_id).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(6)):
            activity.append({**serialize(event), "actor_name": name})
    return {"counts": counts, "recent_jobs": recent, "activity": activity}


def job_summary(db, job):
    version = db.get(ModelVersion, job.model_version_id)
    model = db.get(ModelAsset, version.model_id) if version else None
    dataset_version = db.get(DatasetVersion, job.dataset_version_id) if job.dataset_version_id else None
    dataset = db.get(Dataset, dataset_version.dataset_id) if dataset_version else None
    return {**serialize(job, exclude={"artifact_key"}), "model_name": model.name if model else None,
            "model_version": version.version if version else None, "task_type": model.task_type if model else None,
            "dataset_name": dataset.name if dataset else None, "dataset_number": dataset_version.number if dataset_version else None}


def category_condition(category):
    if category == "trained":
        return ModelVersion.source_ref.startswith("artifact://", autoescape=True)
    if category == "network":
        return ModelVersion.source_ref.startswith("builtin://", autoescape=True)
    if category == "prebuilt":
        return ~ModelVersion.source_ref.startswith("artifact://", autoescape=True) & ~ModelVersion.source_ref.startswith("builtin://", autoescape=True)
    return None


def model_catalog(db, actor, workspace_id, q, task_type, category, page, page_size):
    workspace_access(db, actor, workspace_id, "models.read")
    query = select(ModelAsset).where(ModelAsset.workspace_id == workspace_id)
    if task_type:
        query = query.where(ModelAsset.task_type == task_type)
    condition = category_condition(category)
    if condition is not None:
        query = query.where(ModelAsset.id.in_(select(ModelVersion.model_id).where(condition)))
    rows, pagination = page_data(db, search_query(query, q, ModelAsset.name).order_by(ModelAsset.created_at.desc()), page, page_size)
    ids = [row["id"] for row in rows]
    versions = select(ModelVersion).where(ModelVersion.model_id.in_(ids)).order_by(ModelVersion.created_at.desc(), ModelVersion.id.desc())
    if condition is not None:
        versions = versions.where(condition)
    latest = {}
    for version in db.scalars(versions):
        latest.setdefault(version.model_id, version)
    for row in rows:
        version = latest.get(row["id"])
        source = version.source_ref if version else row["source_ref"]
        row["category"] = "trained" if source.startswith("artifact://") else "network" if source.startswith("builtin://") else "prebuilt"
        row["latest_version"] = serialize(version) if version else None
        source_job = db.scalar(select(Job).where(Job.output_model_version_id == version.id)) if version and source.startswith("artifact://") else None
        row["source_job_id"] = source_job.id if source_job else None
        row["result"] = source_job.result if source_job and "training.read" in effective_policy(db, actor)[0] else {}
    return rows, pagination


def dataset_catalog(db, actor, workspace_id, q, task_type, page, page_size):
    workspace_access(db, actor, workspace_id, "datasets.read")
    query = select(Dataset).where(Dataset.workspace_id == workspace_id)
    if task_type:
        query = query.where(Dataset.task_type == task_type)
    rows, pagination = page_data(db, search_query(query, q, Dataset.name).order_by(Dataset.created_at.desc()), page, page_size)
    latest = {}
    for version in db.scalars(select(DatasetVersion).where(DatasetVersion.dataset_id.in_([row["id"] for row in rows])).order_by(DatasetVersion.number.desc())):
        latest.setdefault(version.dataset_id, serialize(version))
    return [{**row, "latest_version": latest.get(row["id"])} for row in rows], pagination


def project_catalog(db, actor, workspace_id, q, page, page_size):
    workspace_access(db, actor, workspace_id, "training.read")
    rows, pagination = page_data(db, search_query(select(Project).where(Project.workspace_id == workspace_id), q, Project.name).order_by(Project.created_at.desc()), page, page_size)
    groups = {row["id"]: [] for row in rows}
    for job in db.scalars(select(Job).where(Job.project_id.in_(groups), Job.kind == "train").order_by(Job.created_at.desc(), Job.id.desc())):
        groups[job.project_id].append(job)
    for row in rows:
        jobs = groups[row["id"]]
        completed = [item for item in jobs if item.status == "succeeded" and isinstance(item.result.get("accuracy"), (float, int))]
        row.update(job_count=len(jobs), active_count=sum(item.status in {"queued", "preparing", "running", "stopping"} for item in jobs),
                   latest_job=job_summary(db, jobs[0]) if jobs else None,
                   best_accuracy=max((item.result["accuracy"] for item in completed), default=None))
    return rows, pagination
