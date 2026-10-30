"""构建最小服务器源码包，排除数据库、凭据和本机运行文件。"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


ROOT = Path(__file__).resolve().parents[1]
TREES = {
    "backend/src": {".py"},
    "backend/migrations": {".py", ".mako"},
    "backend/tests": {".py"},
    "worker/src": {".py"},
    "frontend/live": {".html", ".js", ".css", ".svg", ".png", ".woff2"},
    "frontend/styles": {".css"},
    "frontend/js": {".js"},
    "deploy/server": {".py", ".yaml", ".sh", ".conf", ".service", ".timer"},
}
FILES = (
    "backend/alembic.ini", "backend/pyproject.toml",
    "backend/requirements.txt", "backend/requirements.lock.txt",
    "scripts/seed_application_presets.py",
    "deploy/server/Dockerfile", "deploy/server/.env.example", ".dockerignore",
    "deploy/server/wheels/.keep",
)
REQUIRED = (
    "backend/src/model_platform/main.py", "backend/src/model_platform/web.py",
    "backend/src/model_platform/services/worker_bundle.py",
    "backend/migrations/versions/0003_jobs_training_evaluation_services.py",
    "frontend/live/index.html", "worker/src/training_worker/cli.py",
)


def collect():
    paths = [ROOT / name for name in FILES]
    for relative, extensions in TREES.items():
        directory = ROOT / relative
        if not directory.is_dir():
            raise ValueError(f"必要目录缺失：{relative}")
        paths.extend(path for path in directory.rglob("*")
                     if path.is_file() and path.suffix in extensions
                     and not path.name.endswith(".test.js")
                     and not any(part.startswith(".") or part == "__pycache__"
                                 for part in path.relative_to(ROOT).parts))
    content = {}
    for path in sorted(set(paths)):
        # 拒绝符号链接，避免打包目录之外的私有内容。
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("源码包不接受链接或目录外文件")
        content[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    missing = set(REQUIRED) - content.keys()
    if missing:
        raise ValueError(f"必要文件缺失：{sorted(missing)}")
    return content


def verify(archive_path):
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if any(not member.isfile() for member in members):
            raise ValueError("部署包含非普通文件")
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError("部署包含重复文件名")
        manifest = json.loads(archive.extractfile("release-manifest.json").read())
        expected = {item["path"]: item for item in manifest["files"]}
        if set(names) != set(expected) | {"release-manifest.json"}:
            raise ValueError("部署包与清单不一致")
        for name, item in expected.items():
            content = archive.extractfile(name).read()
            if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError(f"部署包摘要不一致：{name}")
    return len(expected)


def build(output):
    content = collect()
    manifest = {"format_version": 1, "files": [
        {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in content.items()
    ]}
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / "model-platform.tar.gz"
    outputs = (archive_path, output / "release-manifest.json", output / "release.sha256")
    if any(path.exists() for path in outputs):
        raise ValueError("部署输出已存在，请选择新的发布目录")
    with archive_path.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in {**content, "release-manifest.json": manifest_bytes}.items():
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(data), 0o644, 0
                    archive.addfile(info, io.BytesIO(data))
    count = verify(archive_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    outputs[1].write_bytes(manifest_bytes)
    outputs[2].write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")
    return {"archive": str(archive_path), "files": count,
            "bytes": archive_path.stat().st_size, "sha256": digest,
            "archive_verified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
