from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import Revision, Timestamp


class AnnotationBatch(Timestamp, Revision, Base):
    __tablename__ = "annotation_batches"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    name: Mapped[str] = mapped_column(String(100))
    labels: Mapped[list] = mapped_column(JSON, default=list)
    sample_indices: Mapped[list] = mapped_column(JSON)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default="open")
    output_version_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_versions.id"))


class AnnotationResult(Timestamp, Revision, Base):
    __tablename__ = "annotation_results"
    __table_args__ = (UniqueConstraint("batch_id", "sample_index"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("annotation_batches.id"), index=True)
    sample_index: Mapped[int] = mapped_column(Integer)
    value: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(24))
    edited_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    edits: Mapped[dict] = mapped_column(JSON, default=dict)
    origin: Mapped[dict] = mapped_column(JSON, default=dict)


class DataOperation(Timestamp, Revision, Base):
    __tablename__ = "data_operations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(24))
    options: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    output_version_ids: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(String(400), default="")
