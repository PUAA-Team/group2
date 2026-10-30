from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import Revision, Timestamp


class Project(Timestamp, Revision, Base):
    __tablename__ = "training_projects"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Job(Timestamp, Revision, Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("training_projects.id"))
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"))
    dataset_version_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_versions.id"))
    device_kind: Mapped[str] = mapped_column(String(16), default="cpu")
    min_memory_mb: Mapped[int] = mapped_column(Integer, default=0)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("compute_nodes.id"))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    artifact_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    artifact_bytes: Mapped[int | None] = mapped_column(Integer)
    output_model_version_id: Mapped[str | None] = mapped_column(ForeignKey("model_versions.id"))


class Execution(Timestamp, Base):
    __tablename__ = "executions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("compute_nodes.id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("compute_devices.id"))
    status: Mapped[str] = mapped_column(String(24), default="assigned")
    event_seq: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finish_digest: Mapped[str | None] = mapped_column(String(64))


class ExecutionEvent(Timestamp, Base):
    __tablename__ = "execution_events"
    __table_args__ = (UniqueConstraint("execution_id", "seq"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON)


class ServiceCall(Timestamp, Base):
    __tablename__ = "service_calls"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    input: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, default=dict)


class ServiceKey(Timestamp, Base):
    __tablename__ = "service_keys"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
