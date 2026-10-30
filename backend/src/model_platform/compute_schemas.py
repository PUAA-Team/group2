from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from .schemas import Input


class DeviceInput(Input):
    uuid: str = Field(min_length=1, max_length=120)
    kind: Literal["cpu", "cuda"]
    name: str = Field(min_length=1, max_length=160)
    memory_mb: int = Field(ge=0, le=10000000)
    utilization: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    used_memory_mb: int | None = Field(default=None, ge=0)
    driver: str | None = Field(default=None, max_length=40)


class RuntimeInput(Input):
    python_version: str = Field(default="unknown", max_length=40)
    torch_version: str | None = Field(default=None, max_length=60)
    cuda_version: str | None = Field(default=None, max_length=40)
    cuda_available: bool = False
    trainers: list[Literal["text-classifier-v1", "image-classifier-v1", "qwen-lora-v1"]] = Field(default_factory=list, max_length=3)
    inference_contract_version: Literal[0, 1] = 0
    packages: dict[str, str] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=200)


class InventoryInput(Input):
    hostname: str = Field(min_length=1, max_length=160)
    platform: str = Field(max_length=160)
    cpu_count: int = Field(ge=1, le=100000)
    memory_mb: int = Field(ge=0, le=10000000)
    runtime: RuntimeInput = Field(default_factory=RuntimeInput)
    devices: list[DeviceInput] = Field(max_length=64)
    errors: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def distinct_devices(self):
        if sum(device.kind == "cpu" for device in self.devices) != 1:
            raise ValueError("硬件清单必须包含一个 CPU 设备")
        keys = [(device.kind, device.uuid) for device in self.devices]
        if len(keys) != len(set(keys)):
            raise ValueError("硬件清单存在重复设备")
        return self


class EnrollmentInput(Input):
    workspace_id: str
    name: str = Field(min_length=1, max_length=100)
    platform: Literal["windows", "linux", "docker"] = "windows"
    controller_url: HttpUrl
    training_python: str = Field(default="python", min_length=1, max_length=500)
    state_dir: str = Field(default="D:/model-training-worker", min_length=1, max_length=500)
    image: str = Field(default="", max_length=300, pattern=r"^[a-zA-Z0-9_./:@-]*$")
    auto_approve: bool = False

    @model_validator(mode="after")
    def safe_endpoint(self):
        if self.controller_url.username or self.controller_url.password or self.controller_url.query or self.controller_url.fragment:
            raise ValueError("控制端地址不能含凭据、参数或片段")
        if self.platform == "docker" and not self.image:
            raise ValueError("请填写已构建的 Worker 镜像")
        if any("\x00" in value or "\n" in value or "\r" in value for value in [self.training_python, self.state_dir]):
            raise ValueError("路径含非法字符")
        return self


class RegisterInput(Input):
    protocol_version: Literal[1]
    join_code: str = Field(min_length=20, max_length=200)
    installation_id: str = Field(pattern=r"^[a-zA-Z0-9-]{16,64}$")
    machine_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    credential_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    slots: int = Field(default=1, ge=1, le=4)
    inventory: InventoryInput


class HeartbeatInput(Input):
    protocol_version: Literal[1]
    seq: int = Field(ge=1)
    active_executions: list[str] = Field(default_factory=list, max_length=16)
    metrics: list[DeviceInput] = Field(default_factory=list, max_length=64)


class InventoryReport(Input):
    request_id: str
    inventory: InventoryInput


class NodePatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    workspace_id: str | None = None
    approved: bool | None = None
    enabled: bool | None = None


class LocalWorkerInput(Input):
    workspace_id: str
    name: str = Field(default="本机 Worker", min_length=1, max_length=100)
    runtime_id: Literal["torch", "llm"] = "llm"
