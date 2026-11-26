from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import Revision, Timestamp


class NodeSample(Timestamp, Base):
    __tablename__ = "node_samples"
    __table_args__ = (UniqueConstraint("node_id", "seq"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("compute_nodes.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict] = mapped_column(JSON)


class DevicePolicy(Timestamp, Revision, Base):
    __tablename__ = "device_policies"
    id: Mapped[str] = mapped_column(ForeignKey("compute_devices.id"), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class GroupBudget(Timestamp, Revision, Base):
    __tablename__ = "group_budgets"
    id: Mapped[str] = mapped_column(ForeignKey("user_groups.id"), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class WorkspaceBudget(Timestamp, Revision, Base):
    __tablename__ = "workspace_budgets"
    id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class StoredObject(Timestamp, Base):
    __tablename__ = "stored_objects"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("user_groups.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    object_id: Mapped[str] = mapped_column(String(40))
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)


class ExecutionReview(Timestamp, Base):
    __tablename__ = "execution_reviews"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(1000))
    outcome: Mapped[str] = mapped_column(String(16))
