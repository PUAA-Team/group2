from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, text
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
    # machine_id / installation_id 不再全局唯一：已撤销节点不占唯一位，
    # 仅对未撤销节点建部分唯一索引（见 0014 迁移），以便同一台机器
    # 在旧节点被撤销后能以全新节点重新接入，旧记录原样保留。
    __table_args__ = (
        Index("uq_compute_nodes_machine_id_active", "machine_id", unique=True,
              postgresql_where=text("revoked = false"), sqlite_where=text("revoked = 0")),
        Index("uq_compute_nodes_installation_id_active", "installation_id", unique=True,
              postgresql_where=text("revoked = false"), sqlite_where=text("revoked = 0")),
    )
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    installation_id: Mapped[str] = mapped_column(String(64))
    machine_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    credential_digest: Mapped[str] = mapped_column(String(64), unique=True)
    # 凭据过期时间；旧数据为 NULL 时视为未过期，下次注册/轮换后填入。
    credential_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    # 硬件标识只在同一节点内唯一：同一台机器以新节点重新接入时，
    # 会按同一 hardware_id（cpu:<machine_id> / nvidia:<uuid>）重建设备行。
    __table_args__ = (UniqueConstraint("node_id", "hardware_id", name="uq_compute_devices_node_hardware"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("compute_nodes.id"), index=True)
    hardware_id: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(160))
    memory_mb: Mapped[int] = mapped_column(Integer, default=0)
    present: Mapped[bool] = mapped_column(Boolean, default=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    reserved_execution_id: Mapped[str | None] = mapped_column(String(40), unique=True)
