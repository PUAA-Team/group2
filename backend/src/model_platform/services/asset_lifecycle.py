from ..errors import Problem
from sqlalchemy import update
from .common import audit, commit, revision_update


def ensure_active(asset):
    if asset is not None and asset.archived:
        raise Problem(409, 'ASSET_ARCHIVED', '资产已归档，请先恢复后再创建新版本或任务')


def lock_active(db, asset):
    model = type(asset)
    changed = db.execute(update(model).where(model.id == asset.id, model.archived.is_(False))
        .values(revision=model.revision).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise Problem(409, 'ASSET_ARCHIVED', '资产已归档，请先恢复')


def set_archive(db, actor, asset, payload, kind):
    revision_update(db, asset, {'archived': payload.archived}, payload.revision)
    audit(db, actor, f'{kind}.archive' if payload.archived else f'{kind}.restore', asset.id, asset.workspace_id)
    commit(db)
    return {'id': asset.id, 'archived': asset.archived, 'revision': asset.revision}
