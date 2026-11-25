from sqlalchemy import func, select

from ..database import new_id
from ..errors import Problem
from ..models import DatasetVersion
from .common import audit, commit, revision_update
from .dataset_files import parse_samples
from .file_storage import delete_object, read_verified, write_atomic
from .asset_lifecycle import ensure_active
from .budgets import charge_objects


async def store_version(db, settings, actor, dataset, upload, column_mapping=None):
    from .platform_settings import dataset_limits
    settings = dataset_limits(db, settings)
    content = await upload.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise Problem(413, "FILE_TOO_LARGE", "文件超过大小限制")
    from .dataset_mapping import normalize_upload
    filename, content, provenance, _, _ = normalize_upload(content, dataset.task_type, upload.filename, settings.max_samples, column_mapping)
    return store_versions(db, settings, actor, dataset, [(filename, content, provenance)])[0]


def store_versions(db, settings, actor, dataset, files, *, parent=None, finalize=None):
    """多个派生版本及业务发布记录共用一次提交，失败仅清理本次文件。"""
    from .platform_settings import dataset_limits
    settings = dataset_limits(db, settings)
    ensure_active(dataset)
    if parent is not None and parent.dataset_id != dataset.id:
        raise Problem(409, "CONFLICT", "来源版本不属于当前数据集")
    prepared = []
    for filename, content, provenance in files:
        if len(content) > settings.max_upload_bytes:
            raise Problem(413, "FILE_TOO_LARGE", "结果文件超过大小限制")
        _, metadata = parse_samples(content, dataset.task_type, filename, settings.max_samples)
        prepared.append((filename, content, provenance, metadata))
    # 先取得父对象写入锁，再分配版本号；竞争更新由 revision 校验拒绝。
    revision_update(db, dataset, {}, dataset.revision)
    number = (db.scalar(select(func.max(DatasetVersion.number)).where(DatasetVersion.dataset_id == dataset.id)) or 0) + 1
    owned_paths, versions = [], []
    try:
        for offset, (filename, content, provenance, metadata) in enumerate(prepared):
            version_id = new_id("dvr")
            storage_key = f"{dataset.workspace_id}/{dataset.id}/{version_id}.{metadata['format']}"
            charge_objects(db, actor, [{'id': 'dataset:' + version_id, 'workspace_id': dataset.workspace_id,
                'kind': 'dataset', 'object_id': version_id, 'storage_key': storage_key, 'size_bytes': len(content)}])
            path, _, _ = write_atomic(settings, storage_key, content)
            owned_paths.append(storage_key)
            version = DatasetVersion(id=version_id, dataset_id=dataset.id, number=number + offset,
                storage_key=storage_key, filename=filename, parent_version_id=parent.id if parent else None,
                provenance=provenance, **metadata)
            db.add(version)
            versions.append(version)
            audit(db, actor, "dataset_versions.create", version_id, dataset.workspace_id)
        db.flush()
        if finalize:
            finalize(versions)
        commit(db)
        return versions
    except Exception:
        db.rollback()
        # 仅清理本次生成的随机文件；不扫描或删除用户历史资产。
        for key in owned_paths:
            delete_object(settings, key)
        raise


def preview(settings, dataset, version, limit):
    _, content, _ = read_verified(settings, version.storage_key, version.sha256, missing_message="版本文件暂不可读")
    rows, metadata = parse_samples(content, dataset.task_type, version.filename, settings.max_samples)
    if metadata["sha256"] != version.sha256:
        raise Problem(409, "CONFLICT", "版本文件完整性校验失败")
    return {"version_id": version.id, "samples": rows[:limit], "total": version.sample_count}
