from dataclasses import replace

from ..administration_models import PlatformSetting
from ..administration_schemas import PlatformConfig
from ..errors import Problem
from ..models import UserGroup
from .common import audit, commit, revision_update


def platform_config(db):
    record = db.get(PlatformSetting, "platform")
    return PlatformConfig(**(record.value if record else {}))


def config_view(db):
    record = db.get(PlatformSetting, "platform")
    return {**platform_config(db).model_dump(), "revision": record.revision if record else 1}


def save_config(db, actor, payload, expected):
    if payload.default_group_id and not db.get(UserGroup, payload.default_group_id):
        raise Problem(422, "VALIDATION_ERROR", "默认用户组不存在")
    record = db.get(PlatformSetting, "platform")
    revision_update(db, record, {"value": payload.model_dump()}, expected)
    audit(db, actor, "settings.update", "platform")
    commit(db)
    return config_view(db)


def dataset_limits(db, settings):
    config = platform_config(db)
    return replace(settings, max_upload_bytes=min(settings.max_upload_bytes, config.max_upload_mib * 1024 * 1024),
                   max_samples=min(settings.max_samples, config.max_samples))
