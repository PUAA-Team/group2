import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .job_schemas import JobInput
from .schemas import Input

SCOPES = {"configuration", "logs", "text_samples", "image_samples"}
PARAMETERS = {"epochs", "batch_size", "learning_rate", "validation_ratio", "seed", "max_length", "lora_rank"}


class AIPolicyInput(Input):
    revision: int = Field(ge=0)
    enabled: bool = False
    connection_ids: list[str] = Field(default_factory=list, max_length=20)
    scopes: list[Literal["configuration", "logs", "text_samples", "image_samples"]] = Field(default_factory=list, max_length=4)
    daily_requests: int = Field(default=30, ge=1, le=1000)
    max_samples: int = Field(default=5, ge=1, le=20)
    max_characters: int = Field(default=12000, ge=1000, le=30000)
    max_tokens: int = Field(default=1024, ge=128, le=4096)

    @model_validator(mode="after")
    def enabled_options(self):
        if self.enabled and (not self.connection_ids or not self.scopes):
            raise ValueError("启用时请选择连接与外发类别")
        if len(set(self.connection_ids)) != len(self.connection_ids) or len(set(self.scopes)) != len(self.scopes):
            raise ValueError("连接与类别不能重复")
        return self


class AssistantPrepare(Input):
    purpose: Literal["annotation", "parameters", "logs"]
    connection_id: str = Field(min_length=1, max_length=40)
    source_id: str | None = Field(default=None, max_length=40)
    job: JobInput | None = None
    sample_indices: list[int] = Field(default_factory=list, max_length=20)
    log_start: int | None = Field(default=None, ge=1)
    log_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def correct_source(self):
        if self.purpose == "parameters":
            if not self.job or self.job.kind != "train" or self.source_id:
                raise ValueError("参数推荐需要训练配置")
        elif not self.source_id or self.job:
            raise ValueError("请选择对应业务对象")
        if self.purpose == "annotation" and (not self.sample_indices or min(self.sample_indices) < 0 or len(set(self.sample_indices)) != len(self.sample_indices)):
            raise ValueError("请选择不重复的非负样本序号")
        if self.purpose != "annotation" and self.sample_indices:
            raise ValueError("此用途不接收样本序号")
        if self.purpose != "logs" and (self.log_start or self.log_end):
            raise ValueError("此用途不接收日志范围")
        if self.log_start and self.log_end and self.log_start > self.log_end:
            raise ValueError("日志范围无效")
        return self


class AssistantConfirm(Input):
    input_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class AssistantApply(Input):
    fields: list[str] = Field(default_factory=list, max_length=7)
    indices: list[int] = Field(default_factory=list, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class AnnotationSuggestion(Input):
    index: int = Field(ge=0)
    value: str = Field(min_length=1, max_length=16000)
    reason: str = Field(default="", max_length=1000)


class AnnotationOutput(Input):
    samples: list[AnnotationSuggestion] = Field(min_length=1, max_length=20)


class ParameterSuggestion(Input):
    field: Literal["epochs", "batch_size", "learning_rate", "validation_ratio", "seed", "max_length", "lora_rank"]
    value: int | float
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("value", mode="before")
    @classmethod
    def finite_number(cls, value):
        if type(value) not in {int, float} or not math.isfinite(value):
            raise ValueError("参数值需要有限数值")
        return value

    @model_validator(mode="after")
    def integer_fields(self):
        if self.field not in {"learning_rate", "validation_ratio"} and type(self.value) is not int:
            raise ValueError("此参数需要整数")
        return self


class ParameterOutput(Input):
    suggestions: list[ParameterSuggestion] = Field(min_length=1, max_length=7)


class LogCause(Input):
    reason: str = Field(min_length=1, max_length=1000)
    evidence: list[int] = Field(default_factory=list, max_length=20)
    steps: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("steps")
    @classmethod
    def bounded_steps(cls, values):
        if any(not value.strip() or len(value) > 1000 for value in values):
            raise ValueError("排查步骤过长或为空")
        return values


class LogOutput(Input):
    summary: str = Field(min_length=1, max_length=2000)
    causes: list[LogCause] = Field(min_length=1, max_length=6)
    suggestions: list[ParameterSuggestion] = Field(default_factory=list, max_length=7)
