from collections import Counter
from datetime import timedelta, timezone

from sqlalchemy import func, select

from ..database import aware, utcnow
from ..job_models import Job
from ..models import AuditEvent, Dataset, DatasetVersion, Membership, ModelAsset, ModelVersion, User, Workspace
from ..permissions import effective_policy
from .common import page_data, search_query, serialize
from .console import job_summary


def global_catalog(db, kind, q, space, status, job_kind, page, page_size, allowed_kinds):
    model = {"datasets": Dataset, "models": ModelAsset, "jobs": Job, "audit": AuditEvent}[kind]
    query = select(model)
    if space:
        query = query.where(model.workspace_id == space)
    if kind == "jobs":
        query = query.where(Job.kind.in_(allowed_kinds))
        if status:
            query = query.where(Job.status == status)
        if job_kind:
            query = query.where(Job.kind == job_kind)
    if kind == "audit" and status:
        query = query.where(AuditEvent.result == status)
    column = AuditEvent.action if kind == "audit" else model.name
    rows, pagination = page_data(db, search_query(query, q, column).order_by(model.created_at.desc()), page, page_size)
    for row in rows:
        if kind == "jobs":
            row.update(job_summary(db, db.get(Job, row["id"])))
            row.pop("artifact_key", None)
        workspace = db.get(Workspace, row["workspace_id"]) if row.get("workspace_id") else None
        owner_id = row.get("actor_id") or row.get("created_by") or (workspace.owner_id if workspace else None)
        owner = db.get(User, owner_id) if owner_id else None
        row.update(workspace_name=workspace.name if workspace else "全平台", actor_name=owner.display_name if owner else "—")
        if kind in {"datasets", "models"}:
            version_type = DatasetVersion if kind == "datasets" else ModelVersion
            key = version_type.dataset_id if kind == "datasets" else version_type.model_id
            latest = db.scalar(select(version_type).where(key == row["id"]).order_by(version_type.created_at.desc(), version_type.id.desc()).limit(1))
            row["latest_version"] = serialize(latest) if latest else None
    return rows, pagination


def statistics(db, actor, space=None):
    actions, _ = effective_policy(db, actor)
    counts = {}
    for key, model, action in [("users", User, "users.manage"), ("datasets", Dataset, "datasets.read"), ("models", ModelAsset, "models.read")]:
        query = select(func.count()).select_from(model)
        if space and hasattr(model, "workspace_id"):
            query = query.where(model.workspace_id == space)
        if space and model is User:
            query = query.join(Membership, Membership.user_id == User.id).where(Membership.workspace_id == space)
        counts[key] = db.scalar(query) if action in actions else None
    kinds = (["train", "evaluate"] if "training.read" in actions else []) + (["service"] if "services.read" in actions else [])
    query = select(Job).where(Job.kind.in_(kinds))
    if space:
        query = query.where(Job.workspace_id == space)
    jobs = db.scalars(query).all()
    states = Counter(job.status for job in jobs)
    counts.update(jobs=len(jobs), active=sum(states[key] for key in ["preparing", "running", "ready", "stopping"]), queued=states["queued"], failed=states["failed"])
    business_zone = timezone(timedelta(hours=8))
    now = utcnow().astimezone(business_zone); trend = {}
    for day in range(13, -1, -1):
        key = (now - timedelta(days=day)).date().isoformat()
        trend[key] = {"date": key, "train": 0, "evaluate": 0, "service": 0}
    distribution = Counter()
    for job in jobs:
        day = aware(job.created_at).astimezone(business_zone).date().isoformat()
        if day in trend:
            trend[day][job.kind] += 1
        distribution[job.workspace_id] += 1
    spaces = [{"id": item.id, "name": item.name, "jobs": distribution[item.id]} for item in db.scalars(select(Workspace).where(Workspace.id == space) if space else select(Workspace))]
    return {"counts": counts, "states": dict(states), "trend": list(trend.values()), "workspaces": spaces, "timezone": "Asia/Shanghai"}
