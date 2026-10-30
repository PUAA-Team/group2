from typing import Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .permissions import ACTIONS, QUOTAS

TaskType = Literal["text_classification", "image_classification", "llm_sft"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Policy(Input):
    allow_actions: list[str] = Field(default_factory=list)
    deny_actions: list[str] = Field(default_factory=list)
    quota: dict[str, int] = Field(default_factory=dict)

    @field_validator("allow_actions", "deny_actions")
    @classmethod
    def validate_actions(cls, value):
        if set(value) - ACTIONS:
            raise ValueError("包含未知权限")
        return sorted(set(value))

    @field_validator("quota")
    @classmethod
    def validate_quota(cls, value):
        if set(value) - set(QUOTAS) or any(number < 0 for number in value.values()):
            raise ValueError("配额字段未知或存在负数")
        return value


class GroupCreate(Policy):
    name: str = Field(min_length=1, max_length=100)


class GroupPatch(Policy):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class Login(Input):
    account: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("password", mode="before")
    @classmethod
    def preserve_password(cls, value):
        # 密码通过字段配置保留首尾空格，避免静默改变秘密值。
        return value

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserCreate(Policy):
    account: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=256, strict=True)
    group_id: str | None = None
    is_admin: bool = False

    @field_validator("account")
    @classmethod
    def normalize_account(cls, value):
        return value.lower()

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value):
        if not value.strip():
            raise ValueError("显示名称不能为空")
        return value.strip()

    @field_validator("password", mode="before")
    @classmethod
    def password_not_blank(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("密码不能为空")
        return value

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserPatch(Policy):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    active: bool | None = None
    group_id: str | None = None
    is_admin: bool | None = None


class WorkspaceCreate(Input):
    name: str = Field(min_length=1, max_length=100)


class SetupInput(Input):
    account: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=256, strict=True)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    @model_validator(mode="after")
    def validate_credentials(self):
        self.to_user()
        return self

    def to_user(self):
        return UserCreate(**self.model_dump(), is_admin=True)


class MemberInput(Input):
    user_id: str | None = None
    account: str | None = Field(default=None, min_length=3, max_length=64)
    role: Literal["editor", "viewer"]

    @model_validator(mode="after")
    def one_identity(self):
        if bool(self.user_id) == bool(self.account):
            raise ValueError("请选择一个已有用户或填写账号")
        return self


def safe_source(value):
    parsed = urlsplit(value)
    secret_names = {"token", "api_key", "key", "secret", "password", "signature", "access_token", "credential"}
    if parsed.username or parsed.password or any(
        any(word in key.lower() for word in secret_names) for key, _ in parse_qsl(parsed.query)
    ) or parsed.fragment:
        raise ValueError("来源不得包含凭据或片段")
    return value


class ModelCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    task_type: TaskType
    trainer_id: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=2000)
    _source = field_validator("source_ref")(safe_source)


class ModelPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class ModelVersionCreate(Input):
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    source_ref: str = Field(min_length=1, max_length=1000)
    _source = field_validator("source_ref")(safe_source)


class DatasetCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    task_type: TaskType
    description: str = Field(default="", max_length=2000)


class DatasetPatch(ModelPatch):
    pass
