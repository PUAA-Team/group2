from datetime import datetime

from .compute_schemas import InventoryInput
from .governance_schemas import DevicePurpose
from .outputs import Entity, Output, PageEnvelope


class DeviceOut(Entity):
    node_id: str
    hardware_id: str
    kind: str
    name: str
    memory_mb: int
    present: bool
    metrics: dict
    reserved_execution_id: str | None
    status: str
    purpose: DevicePurpose = "shared"
    selectable: bool | None = None


class NodeOut(Entity):
    workspace_id: str
    installation_id: str
    name: str
    approved: bool
    enabled: bool
    revoked: bool
    slots: int
    heartbeat_seq: int
    last_seen_at: datetime | None
    last_inventory_at: datetime | None
    probe_request_id: str | None
    inventory: InventoryInput
    active_executions: list[str]
    revision: int
    status: str
    online: bool
    devices: list[DeviceOut]


class NodeCounts(Output):
    total: int
    online: int


class DeviceCounts(Output):
    total: int
    occupied: int
    disconnected_occupied: int


class ResourceSummary(Output):
    nodes: NodeCounts
    cpu: DeviceCounts
    cuda: DeviceCounts


class NodePage(PageEnvelope[NodeOut]):
    summary: ResourceSummary | None = None


class EnrollmentOut(Output):
    id: str
    expires_at: datetime
    command: str
    display_command: str
    bundle_sha256: str
    platform: str
    controller_url: str


class EnrollmentStatus(Output):
    id: str
    status: str
    node_id: str | None
    expires_at: datetime


class WorkerReceipt(Output):
    node_id: str
    approved: bool
    enabled: bool
    heartbeat_seconds: int
    next_seq: int
    credential_expires_at: datetime | None = None


class CredentialReceipt(WorkerReceipt):
    # 轮换出的新凭据只在本次响应里返回一次，服务端只存摘要。
    credential: str


class HeartbeatReceipt(WorkerReceipt):
    probe_request_id: str | None
    controls: list[dict]
