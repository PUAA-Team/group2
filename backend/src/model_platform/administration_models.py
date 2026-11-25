from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import Revision, Timestamp


class PlatformSetting(Timestamp, Revision, Base):
    __tablename__ = "platform_settings"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelConnection(Timestamp, Revision, Base):
    __tablename__ = "model_connections"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    endpoint: Mapped[str] = mapped_column(String(1000))
    model: Mapped[str] = mapped_column(String(200))
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    secret_ref: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    health: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Invitation(Timestamp, Base):
    __tablename__ = "user_invitations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("user_groups.id"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    role: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class WorkspaceInvite(Timestamp, Base):
    __tablename__ = "workspace_invites"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    code_digest: Mapped[str] = mapped_column(String(64), unique=True)
    code_preview: Mapped[str] = mapped_column(String(16))
    role: Mapped[str] = mapped_column(String(10))
    require_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    max_uses: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class WorkspaceJoinRequest(Timestamp, Base):
    __tablename__ = "workspace_join_requests"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", "invite_id"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    invite_id: Mapped[str] = mapped_column(ForeignKey("workspace_invites.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    requested_role: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
