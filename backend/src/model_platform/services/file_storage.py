import hashlib

from ..errors import Problem
from .dataset_files import controlled_path


def resolve_key(settings, storage_key):
    return controlled_path(settings, storage_key)


def write_atomic(settings, storage_key, content: bytes, *, staged_name: str | None = None):
    """原子写入存储对象：先写临时文件，再整体替换为目标路径。

    staged_name 为调用方指定的临时文件名（仅文件名，不含路径分隔符，
    供并发上传隔离使用，如 ``{execution.id}.{uuid}.zip``）；不指定时
    沿用旧的 ``.upload`` 后缀。临时文件与目标文件在同一目录，保证
    replace() 为同文件系统内的原子操作。
    """
    if staged_name is not None and ("/" in staged_name or "\\" in staged_name):
        raise ValueError("staged_name 只能是文件名")
    path = resolve_key(settings, storage_key)
    staged = path.parent / staged_name if staged_name else path.with_suffix(".upload")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with staged.open("wb") as stream:
            stream.write(content)
        staged.replace(path)
    except Exception:
        staged.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        raise
    return path, hashlib.sha256(content).hexdigest(), len(content)


def read_verified(settings, storage_key, expected_sha256=None, *, missing_message="文件缺失"):
    path = resolve_key(settings, storage_key)
    if not path.is_file():
        raise Problem(409, "FILE_NOT_READY", missing_message)
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if expected_sha256 and actual != expected_sha256:
        raise Problem(409, "FILE_CORRUPTED", "文件完整性校验失败")
    return path, content, actual


def delete_object(settings, storage_key):
    if not storage_key:
        return
    try:
        resolve_key(settings, storage_key).unlink(missing_ok=True)
    except (OSError, Problem):
        pass
