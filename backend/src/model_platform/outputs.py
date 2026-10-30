from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Envelope(Output, Generic[T]):
    data: T
    request_id: str


class ErrorDetail(Output):
    loc: list[str | int]
    type: str
    message: str


class ErrorBody(Output):
    code: str
    message: str
    details: list[ErrorDetail]


class ErrorEnvelope(Output):
    error: ErrorBody
    request_id: str


class Pagination(Output):
    page: int
    page_size: int
    total: int


class PageEnvelope(Envelope[list[T]], Generic[T]):
    pagination: Pagination


class Entity(Output):
    id: str
    created_at: datetime


class PolicyFields(Output):
    allow_actions: list[str]
    deny_actions: list[str]
    quota: dict[str, int]


class GroupOut(Entity, PolicyFields):
    name: str
    revision: int


class UserOut(Entity, PolicyFields):
    account: str
    display_name: str
    group_id: str | None
    is_admin: bool
    active: bool
    revision: int


class PolicySummary(Output):
    actions: list[str]
    quota: dict[str, int]


class SessionOut(Output):
    user: UserOut
    csrf_token: str
    access: PolicySummary


class SetupState(Output):
    initialized: bool
    enabled: bool


class WorkspaceOut(Entity):
    name: str
    owner_id: str
    revision: int


class MemberOut(Output):
    workspace_id: str
    user_id: str
    role: str


class MemberSummaryOut(MemberOut):
    account: str
    display_name: str
    active: bool


class AccessOut(Output):
    actions: list[str]
    quota: dict[str, int]
    role: str


class DatasetOut(Entity):
    workspace_id: str
    name: str
    task_type: str
    description: str
    revision: int


class ModelOut(DatasetOut):
    trainer_id: str
    source_ref: str


class ModelVersionOut(Entity):
    model_id: str
    version: str
    source_ref: str
    status: str
    created_by: str


class DatasetVersionOut(Entity):
    dataset_id: str
    number: int
    format: str
    filename: str
    sha256: str
    size_bytes: int
    sample_count: int
    status: str
    parent_version_id: str | None
    provenance: dict


class PreviewOut(Output):
    version_id: str
    samples: list[dict[str, str]]
    total: int


class TemplateOut(Output):
    id: str
    task_type: str
    name: str
    execution_available: bool


class AuditOut(Entity):
    actor_id: str
    workspace_id: str | None
    action: str
    target_id: str
    result: str
