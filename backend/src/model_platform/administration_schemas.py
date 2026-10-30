from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, field_validator, model_validator

from .schemas import Input, UserCreate


class PlatformConfig(Input):
    platform_name: str = Field(default="模训平台", min_length=1, max_length=40)
    invitations_enabled: bool = True
    max_upload_mib: int = Field(default=10, ge=1, le=10)
    max_samples: int = Field(default=10000, ge=2, le=10000)
    global_concurrent_jobs: int = Field(default=16, ge=1, le=100)


class ConnectionInput(Input):
    name: str = Field(min_length=1, max_length=100)
    endpoint: str = Field(min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=200)
    capabilities: list[Literal["text", "vision", "json"]] = Field(default_factory=lambda: ["text"], min_length=1, max_length=3)
    secret: str | None = Field(default=None, min_length=1, max_length=512)
    active: bool = True

    @field_validator("endpoint")
    @classmethod
    def endpoint_format(cls, value):
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("模型地址需要不含凭据、查询参数与片段的HTTPS地址")
        return value.rstrip("/")

    @field_validator("secret")
    @classmethod
    def secret_format(cls, value):
        if value is not None and any(ord(char) < 33 or ord(char) > 126 for char in value):
            raise ValueError("密钥包含无效字符")
        return value


class InviteInput(Input):
    workspace_id: str
    group_id: str | None = None
    role: Literal["editor", "viewer"] = "editor"
    days: int = Field(default=3, ge=1, le=7)


class RegisterInput(Input):
    account: str
    display_name: str
    password: str
    invitation: str = Field(min_length=20, max_length=200)

    @model_validator(mode="after")
    def validate_credentials(self):
        try:
            self.user_payload()
        except ValidationError:
            raise ValueError("账号、姓名或密码不符合要求") from None
        return self

    def user_payload(self):
        return UserCreate(account=self.account, display_name=self.display_name, password=self.password)

    model_config = {"extra": "forbid", "str_strip_whitespace": False}


class PasswordInput(Input):
    password: str = Field(min_length=12, max_length=256)
    current_password: str | None = Field(default=None, max_length=256)
    model_config = {"extra": "forbid", "str_strip_whitespace": False}


class ProfileInput(Input):
    display_name: str = Field(min_length=1, max_length=100)
