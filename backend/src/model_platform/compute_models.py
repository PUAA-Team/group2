from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import Revision, Timestamp


class Enrollment(Timestamp, Base):
    __tablename__ = "resource_enrollments"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    code_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    consumed_node_id: Mapped[str | None] = mapped_column(String(40))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ComputeNode(Timestamp, Revision, Base):
    __tablename__ = "compute_nodes"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    installation_id: Mapped[str] = mapped_column(String(64), unique=True)
    machine_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    credential_digest: Mapped[str] = mapped_column(String(64), unique=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    slots: Mapped[int] = mapped_column(Integer, default=1)
    heartbeat_seq: Mapped[int] = mapped_column(Integer, default=0)
    heartbeat_digest: Mapped[str | None] = mapped_column(String(64))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_inventory_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    probe_request_id: Mapped[str | None] = mapped_column(String(40))
    inventory: Mapped[dict] = mapped_column(JSON, default=dict)
    active_executions: Mapped[list] = mapped_column(JSON, default=list)


class ComputeDevice(Timestamp, Base):
    __tablename__ = "compute_devices"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("compute_nodes.id"), index=True)
    hardware_id: Mapped[str] = mapped_column(String(160), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(160))
    memory_mb: Mapped[int] = mapped_column(Integer, default=0)
    present: Mapped[bool] = mapped_column(Boolean, default=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    reserved_execution_id: Mapped[str | None] = mapped_column(String(40), unique=True)
