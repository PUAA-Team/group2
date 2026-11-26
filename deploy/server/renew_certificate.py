"""续期IP证书，只有证书发生变化时才重新加载网关。"""
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess


def renew(root, address, dry_run=False):
    runtime = root / "runtime"
    certificate = runtime / "certificates/live" / address / "fullchain.pem"
    if not certificate.is_file():
        raise ValueError("请先完成证书首次签发")
    before = hashlib.sha256(certificate.read_bytes()).digest()
    if not dry_run:
        backup_dir = runtime / f"certificates.bak.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        shutil.copytree(runtime / "certificates", backup_dir, symlinks=True, dirs_exist_ok=True)
    volumes = []
    for name, target in (("certificates", "/etc/letsencrypt"),
                         ("certbot-work", "/var/lib/letsencrypt"),
                         ("certbot-logs", "/var/log/letsencrypt")):
        volumes.extend(["-v", f"{runtime / name}:{target}"])
    base = ["docker", "run", "--rm", "--pull=never", "--network", "host"]
    options = ["certbot/certbot:latest", "renew", "--non-interactive", "--quiet",
               "--no-random-sleep-on-renew", "--agree-tos", "--register-unsafely-without-email"]
    if dry_run:
        options.append("--dry-run")
    command = [*base, *volumes, *options]
    subprocess.run(command, check=True)
    if dry_run:
        if hashlib.sha256(certificate.read_bytes()).digest() != before:
            raise RuntimeError("续期演练不应替换正式证书")
        print("续期演练通过，正式证书未改动")
        return
    if hashlib.sha256(certificate.read_bytes()).digest() != before:
        project = root / "current/deploy/server"
        command = ["docker", "compose", "--env-file", str(project / ".env"),
                   "-f", str(project / "compose.yaml"), "exec", "-T", "gateway"]
        subprocess.run([*command, "nginx", "-t"], check=True)
        subprocess.run([*command, "nginx", "-s", "reload"], check=True)
        print("证书已续期，网关已重新加载")
    else:
        print("证书尚未到续期时间，网关保持运行")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/srv/model-platform"))
    parser.add_argument("--ip", default="47.93.115.188")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    renew(arguments.root, arguments.ip, arguments.dry_run)
