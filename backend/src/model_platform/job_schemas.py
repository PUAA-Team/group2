import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .schemas import Input


class ProjectInput(Input):
    name: str = Field(min_length=1, max_length=100)


class InferenceConfig(Input):
    mode: Literal["generate", "label"] = "generate"
    instruction: str = Field(default="", max_length=2048)
    labels: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, values):
        if any(not value or value != value.strip() or len(value) > 64 or any(ord(char) < 32 for char in value) for value in values) or len(set(values)) != len(values):
            raise ValueError("标签须为不重复的1～64字单行文本")
        return values

    @model_validator(mode="after")
    def classification_contract(self):
        if self.mode == "label" and (not self.instruction.strip() or len(self.labels) < 2):
            raise ValueError("标签分类需要任务指令和至少两个标签")
        if self.mode == "generate" and self.labels:
            raise ValueError("自由生成模式不使用固定标签")
        return self


class TrainConfig(Input):
    epochs: int = Field(default=5, ge=1, le=100)
    batch_size: int = Field(default=8, ge=1, le=64)
    learning_rate: float = Field(default=0.01, gt=0, le=1, allow_inf_nan=False)
    validation_ratio: float = Field(default=0.2, ge=0.1, le=0.5, allow_inf_nan=False)
    seed: int = Field(default=42, ge=0, le=2147483647)
    max_length: int = Field(default=128, ge=32, le=512)
    lora_rank: Literal[4, 8, 16] = 4
    inference: InferenceConfig | None = None


class JobInput(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["train", "evaluate", "service"] = "train"
    project_id: str | None = None
    model_version_id: str
    dataset_version_id: str | None = None
    device_kind: Literal["cpu", "cuda"] = "cpu"
    min_memory_mb: int = Field(default=0, ge=0, le=1048576)
    node_id: str | None = None
    priority: int = Field(default=0, ge=0, le=10)
    config: TrainConfig = Field(default_factory=TrainConfig)

    @model_validator(mode="after")
    def needs_data(self):
        if self.kind != "service" and not self.dataset_version_id:
            raise ValueError("训练和评估需要数据版本")
        return self


class EventInput(Input):
    seq: int = Field(ge=1)
    type: Literal["log", "metric", "started", "ready"]
    payload: dict

    @field_validator("payload")
    @classmethod
    def bounded(cls, value):
        import json
        if len(json.dumps(value, allow_nan=False)) > 8192:
            raise ValueError("事件过长")
        return value


class FinishInput(Input):
    status: Literal["succeeded", "failed", "stopped"]
    result: dict = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=2000)
    _bounded = field_validator("result")(EventInput.bounded.__func__)


class ClaimInput(Input):
    known_executions: list[str] = Field(default_factory=list, max_length=4)


class CallInput(Input):
    text: str | None = Field(default=None, min_length=1, max_length=4096)
    image_base64: str | None = Field(default=None, min_length=1, max_length=1500000)
    max_new_tokens: int = Field(default=32, ge=1, le=128)

    @model_validator(mode="after")
    def one_input(self):
        if bool(self.text) == bool(self.image_base64):
            raise ValueError("请选择文本或图片输入")
        return self


class CallResult(Input):
    status: Literal["succeeded", "failed"]
    result: dict
    _bounded = field_validator("result")(EventInput.bounded.__func__)


class KeyInput(Input):
    name: str = Field(min_length=1, max_length=100)
    job_id: str
    days: int = Field(default=30, ge=1, le=365)
