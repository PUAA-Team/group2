from sqlalchemy import Boolean, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import Revision, Timestamp


class TrainingParameterTemplate(Timestamp, Revision, Base):
    __tablename__ = 'training_parameter_templates'
    __table_args__ = (UniqueConstraint('workspace_id', 'name'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    task_type: Mapped[str] = mapped_column(String(40))
    trainer_id: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
