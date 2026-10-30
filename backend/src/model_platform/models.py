from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, utcnow


class Timestamp:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Revision:
    revision: Mapped[int] = mapped_column(Integer, default=1)


class UserGroup(Timestamp, Revision, Base):
    __tablename__ = "user_groups"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    allow_actions: Mapped[list] = mapped_column(JSON, default=list)
    deny_actions: Mapped[list] = mapped_column(JSON, default=list)
    quota: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Timestamp, Revision, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("user_groups.id"))
    allow_actions: Mapped[list] = mapped_column(JSON, default=list)
    deny_actions: Mapped[list] = mapped_column(JSON, default=list)
    quota: Mapped[dict] = mapped_column(JSON, default=dict)


class SessionToken(Timestamp, Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(Timestamp, Revision, Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Membership(Base):
    __tablename__ = "memberships"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(10))


class ModelAsset(Timestamp, Revision, Base):
    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    task_type: Mapped[str] = mapped_column(String(32))
    trainer_id: Mapped[str] = mapped_column(String(64))
    source_ref: Mapped[str] = mapped_column(String(1000))
    description: Mapped[str] = mapped_column(Text, default="")


class ModelVersion(Timestamp, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id"), index=True)
    version: Mapped[str] = mapped_column(String(64))
    source_ref: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(24), default="registered")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Dataset(Timestamp, Revision, Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    task_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")


class DatasetVersion(Timestamp, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "number"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(16))
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sample_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    parent_version_id: Mapped[str | None] = mapped_column(String(40))
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditEvent(Timestamp, Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(40))
    result: Mapped[str] = mapped_column(String(24), default="success")
