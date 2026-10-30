from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import Revision, Timestamp


class WorkspaceAIPolicy(Timestamp, Revision, Base):
    __tablename__ = "workspace_ai_policies"
    id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class AssistantRequest(Timestamp, Revision, Base):
    __tablename__ = "assistant_requests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(24))
    connection_id: Mapped[str] = mapped_column(ForeignKey("model_connections.id"))
    connection_revision: Mapped[int] = mapped_column(Integer)
    policy_revision: Mapped[int] = mapped_column(Integer)
    source: Mapped[dict] = mapped_column(JSON)
    messages: Mapped[list] = mapped_column(JSON)
    preview: Mapped[dict] = mapped_column(JSON)
    input_digest: Mapped[str] = mapped_column(String(64))
    max_tokens: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="preview", index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[dict] = mapped_column(JSON, default=dict)


class AssistantAdoption(Timestamp, Base):
    __tablename__ = "assistant_adoptions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("assistant_requests.id"), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    payload_digest: Mapped[str] = mapped_column(String(64))
    target: Mapped[dict] = mapped_column(JSON)
