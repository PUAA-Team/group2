from typing import Literal

from pydantic import Field, field_validator, model_validator

from .schemas import Input

EDIT_FIELDS = {"input", "instruction"}


class AnnotationInput(Input):
    name: str = Field(min_length=1, max_length=100)
    version_id: str
    labels: list[str] = Field(default_factory=list, max_length=32)
    limit: int = Field(default=100, ge=1, le=10000)
    assigned_to: str | None = None

    @model_validator(mode="after")
    def unique_labels(self):
        self.labels = [label.strip() for label in self.labels]
        if any(not label or len(label) > 64 for label in self.labels) or len(set(self.labels)) != len(self.labels):
            raise ValueError("标签需要非空、唯一且不超过64字")
        return self


class ResultInput(Input):
    value: str = Field(min_length=1, max_length=16000)
    revision: int = Field(ge=0)
    submit: bool = False
    # 指令标注可顺带修订输入与指令；其它任务类型拒绝该字段。
    edits: dict[str, str] = Field(default_factory=dict)

    @field_validator("edits")
    @classmethod
    def known_edits(cls, value):
        if set(value) - EDIT_FIELDS:
            raise ValueError("仅支持修改输入与指令")
        if any(len(text) > 16000 or (key == "instruction" and not text.strip()) for key, text in value.items()):
            raise ValueError("指令不能为空，字段内容不超过16000字")
        return value


class ReviewInput(Input):
    indices: list[int] = Field(min_length=1, max_length=10000)
    decision: Literal["approved", "rejected"]
    revision: int = Field(ge=1)


class ProcessingOptions(Input):
    seed: int = Field(default=42, ge=0, le=2147483647)
    deduplicate: bool = True
    trim: bool = True
    drop_unlabeled: bool = False
    label_map: dict[str, str] = Field(default_factory=dict, max_length=32)
    train_ratio: float = Field(default=0.8, ge=0.1, le=0.9)
    validation_ratio: float = Field(default=0.1, ge=0.05, le=0.4)
    methods: list[Literal["flip", "brightness", "noise", "punctuation"]] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def valid_options(self):
        if self.train_ratio + self.validation_ratio > 0.95:
            raise ValueError("测试集比例至少为5%")
        if any(not key.strip() or not value.strip() or len(value) > 64 for key, value in self.label_map.items()):
            raise ValueError("标签映射需要非空且不超过64字")
        if len(set(self.methods)) != len(self.methods):
            raise ValueError("增强方法不能重复")
        return self


class OperationInput(Input):
    name: str = Field(min_length=1, max_length=100)
    version_id: str
    kind: Literal["clean", "split", "augment"]
    options: ProcessingOptions = Field(default_factory=ProcessingOptions)
