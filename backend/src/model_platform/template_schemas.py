from pydantic import Field, model_validator

from .job_schemas import TrainConfig
from .schemas import Input, TaskType


class TemplateConfig(TrainConfig):
    @model_validator(mode='after')
    def training_only(self):
        if self.inference is not None:
            raise ValueError('参数模板不包含服务推理配置')
        return self


class TemplateEdit(Input):
    name: str = Field(min_length=1, max_length=100)
    config: TemplateConfig


class TemplateCreate(TemplateEdit):
    task_type: TaskType
    trainer_id: str = Field(min_length=1, max_length=64)


class TemplateArchive(Input):
    archived: bool


class TemplateResolve(Input):
    model_version_id: str = Field(min_length=1, max_length=40)
