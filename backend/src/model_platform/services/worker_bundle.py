import hashlib
import io
from pathlib import Path
import zipfile


def build_bundle(settings):
    source = Path(__file__).resolve().parents[4] / "worker" / "src"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        files = [(path.relative_to(source).as_posix(), path.read_bytes()) for path in sorted(source.rglob("*.py"))]
        files.append(("__main__.py", b"from training_worker.cli import main\nmain()\n"))
        for name, content in files:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, content)
    content = stream.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    target = settings.runtime_dir / "bundles" / f"worker-{digest}.pyz"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)
    return target, digest
