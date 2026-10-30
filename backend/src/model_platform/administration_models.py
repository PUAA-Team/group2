from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
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
