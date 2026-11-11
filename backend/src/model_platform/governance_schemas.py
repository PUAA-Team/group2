from typing import Literal

from pydantic import Field, field_validator

from .schemas import Input

DevicePurpose = Literal["shared", "train_eval", "inference"]


class DevicePolicyInput(Input):
    revision: int = Field(ge=0)
    enabled: bool = True
    allow_users: list[str] = Field(default_factory=list, max_length=100)
    allow_groups: list[str] = Field(default_factory=list, max_length=100)
    deny_users: list[str] = Field(default_factory=list, max_length=100)
    deny_groups: list[str] = Field(default_factory=list, max_length=100)
    purpose: DevicePurpose = "shared"

    @field_validator("allow_users", "allow_groups", "deny_users", "deny_groups")
    @classmethod
    def identifiers(cls, values):
        if any(not value or len(value) > 40 for value in values) or len(values) != len(set(values)):
            raise ValueError("授权对象无效或重复")
        return values


class BudgetInput(Input):
    revision: int = Field(ge=0)
    gpu_count: int | None = Field(default=None, ge=0, le=100000)
    concurrent_jobs: int | None = Field(default=None, ge=0, le=100000)
    storage_gib: int | None = Field(default=None, ge=0, le=1000000)


class ArchiveInput(Input):
    revision: int = Field(ge=1)
    archived: bool


class ReconcileInput(Input):
    revision: int = Field(ge=1)
    process_exit_confirmed: Literal[True]
    reason: str = Field(min_length=5, max_length=1000)
    outcome: Literal["failed", "stopped"]
