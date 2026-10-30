from sqlalchemy import func, select

from ..database import new_id
from ..errors import Problem
from ..models import DatasetVersion
from .common import audit, commit, revision_update
from .dataset_files import controlled_path, parse_samples


async def store_version(db, settings, actor, dataset, upload):
    from .platform_settings import dataset_limits
    settings = dataset_limits(db, settings)
    content = await upload.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise Problem(413, "FILE_TOO_LARGE", "文件超过大小限制")
    return store_versions(db, settings, actor, dataset, [(upload.filename, content, {})])[0]


def store_versions(db, settings, actor, dataset, files, *, parent=None, finalize=None):
    """多个派生版本及业务发布记录共用一次提交，失败仅清理本次文件。"""
    from .platform_settings import dataset_limits
    settings = dataset_limits(db, settings)
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
            path = controlled_path(settings, storage_key)
            staged = path.with_suffix(".upload")
            path.parent.mkdir(parents=True, exist_ok=True)
            owned_paths.extend([staged, path])
            with staged.open("xb") as stream:
                stream.write(content)
            staged.replace(path)
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
        for path in owned_paths:
            path.unlink(missing_ok=True)
        raise


def preview(settings, dataset, version, limit):
    path = controlled_path(settings, version.storage_key)
    if not path.is_file():
        raise Problem(503, "NOT_READY", "版本文件暂不可读")
    rows, metadata = parse_samples(path.read_bytes(), dataset.task_type, version.filename, settings.max_samples)
    if metadata["sha256"] != version.sha256:
        raise Problem(409, "CONFLICT", "版本文件完整性校验失败")
    return {"version_id": version.id, "samples": rows[:limit], "total": version.sample_count}
