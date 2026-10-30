"""仅在training-demo服务器执行B3发布；正式备份全部留在服务器。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path("/srv/model-platform")
RELEASE = ROOT / "releases/20261029-13b3"
COMPAT = ROOT / "releases/20261029-13b2-compat05"
BACKUP = ROOT / "backups/pre-stage13-b3-20261029"
ARCHIVE = ROOT / "staging/stage13-b3.tar.gz"
SHA = "b66726aead4a0d07560017a385e230e1709e82eeb7f3795a94686c6a131d4385"
TABLES = ("users", "workspaces", "models", "model_versions", "datasets", "dataset_versions", "jobs", "compute_nodes")


def compose(path):
    return ["docker", "compose", "--env-file", str(path / "deploy/server/.env"), "-f", str(path / "deploy/server/compose.yaml")]


def run(command, log):
    with log.open("ab") as output:
        subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)


def records(path):
    sql = "select json_build_object(" + ",".join(f"'{table}',(select coalesce(json_agg(id),'[]') from {table})" for table in TABLES) + ")"
    result = subprocess.run(compose(path) + ["exec", "-T", "db", "psql", "-U", "postgres", "-d", "model_platform", "-At", "-c", sql], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def environment(path, source):
    original = (source / "deploy/server/.env").read_text()
    lines = ["RELEASE_ID=" + path.name if line.startswith("RELEASE_ID=") else line for line in original.splitlines()]
    assert any(line.startswith("RELEASE_ID=") for line in lines)
    target = path / "deploy/server/.env"
    target.write_text("\n".join(lines) + "\n")
    target.chmod(0o600)


def main():
    assert os.name == "posix" and ROOT.is_dir(), "仅允许在指定Linux服务器运行"
    previous = (ROOT / "current").resolve()
    assert previous == ROOT / "releases/20261029-13b2"
    assert not any(path.exists() for path in (RELEASE, COMPAT, BACKUP)), "发布目录已存在，须核查现场后续行"
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == SHA
    BACKUP.mkdir(mode=0o700)
    RELEASE.mkdir()
    with tarfile.open(ARCHIVE, "r:gz") as archive:
        manifest = json.loads(archive.extractfile("release-manifest.json").read())
        entries = {item["path"]: item for item in manifest["files"]}
        names = set()
        for member in archive.getmembers():
            assert member.isfile() and member.name not in names
            target = (RELEASE / member.name).resolve()
            assert target.is_relative_to(RELEASE) and "\\" not in member.name
            names.add(member.name)
            content = archive.extractfile(member).read()
            if member.name != "release-manifest.json":
                expected = entries[member.name]
                assert len(content) == expected["bytes"] and hashlib.sha256(content).hexdigest() == expected["sha256"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        assert names == set(entries) | {"release-manifest.json"}
    wheels = list((previous / "deploy/server/wheels").glob("*.whl"))
    assert len(wheels) == 32
    for wheel in wheels:
        target = RELEASE / "deploy/server/wheels" / wheel.name
        shutil.copy2(wheel, target)
        assert hashlib.sha256(wheel.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest()
    environment(RELEASE, previous)
    # 兼容回退只放宽旧应用健康检查，不删除新表和新数据。
    shutil.copytree(previous, COMPAT)
    environment(COMPAT, previous)
    path = COMPAT / "backend/src/model_platform/main.py"
    original = path.read_text()
    assert original.count("if version != expected_schema:") == 1
    path.write_text(original.replace("if version != expected_schema:", 'if version not in {expected_schema, "0005_data"}:'))
    print("building_compatible_rollback", flush=True)
    run(compose(COMPAT) + ["build", "api"], BACKUP / "build-compat.log")
    run(compose(COMPAT) + ["run", "--rm", "--no-deps", "api", "test", "/app/backend/tests/test_runtime.py", "-q", "-x", "-o", "cache_dir=/runtime/test-runs/b3-compat-cache", "--basetemp", "/runtime/test-runs/b3-compat"], BACKUP / "compat-tests.log")
    print("building_b3", flush=True)
    run(compose(RELEASE) + ["build", "api"], BACKUP / "build.log")
    print("linux_isolated_tests", flush=True)
    run(compose(RELEASE) + ["run", "--rm", "--no-deps", "api", "test", "/app/backend/tests", "-q", "-x", "-o", "cache_dir=/runtime/test-runs/b3-cache", "--basetemp", "/runtime/test-runs/b3", "--junitxml", "/runtime/test-runs/b3.xml"], BACKUP / "linux-tests.log")
    tests = ET.parse(ROOT / "runtime/app/test-runs/b3.xml").getroot()
    counts = {key: sum(int(suite.attrib[key]) for suite in tests.findall("testsuite")) for key in ("tests", "failures", "errors", "skipped")}
    assert counts == {"tests": 94, "failures": 0, "errors": 0, "skipped": 0}, counts
    before = records(previous)
    before_path = BACKUP / "before.json"
    before_path.write_text(json.dumps(before))
    before_path.chmod(0o600)
    print("backing_up_server_only", flush=True)
    with (BACKUP / "platform.dump").open("xb") as output:
        subprocess.run(compose(previous) + ["exec", "-T", "db", "pg_dump", "-U", "postgres", "-d", "model_platform", "-Fc"], stdout=output, check=True)
    (BACKUP / "platform.dump").chmod(0o600)
    with tarfile.open(BACKUP / "application-files.tar.gz", "w:gz") as archive:
        for name in ("storage", "private"):
            source = ROOT / "runtime/app" / name
            if source.exists():
                archive.add(source, arcname=name)
    (BACKUP / "application-files.tar.gz").chmod(0o600)
    shutil.copy2(previous / "deploy/server/.env", BACKUP / "compose.env")
    (BACKUP / "compose.env").chmod(0o600)
    print("migrating_0005_data", flush=True)
    run(compose(RELEASE) + ["run", "--rm", "--no-deps", "migrate"], BACKUP / "migration.log")
    temporary = ROOT / "current-stage13-b3"
    assert not temporary.exists() and not temporary.is_symlink()
    temporary.symlink_to(RELEASE)
    temporary.replace(ROOT / "current")
    run(compose(RELEASE) + ["up", "-d", "--no-deps", "api", "operations"], BACKUP / "activation.log")
    ready = None
    for _ in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:18000/readyz", timeout=2) as result:
                ready = json.load(result)["data"]
            if ready["schema"] == "0005_data":
                break
        except OSError:
            time.sleep(1)
    assert ready and ready["schema"] == "0005_data"
    run(compose(RELEASE) + ["exec", "-T", "gateway", "nginx", "-s", "reload"], BACKUP / "activation.log")
    with urllib.request.urlopen("https://47.93.115.188:5488/", timeout=10) as result:
        assert "stage13-3" in result.read().decode()
    after = records(RELEASE)
    assert all(set(ids) <= set(after[table]) for table, ids in before.items())
    status = subprocess.run(compose(RELEASE) + ["ps", "--format", "json", "operations"], capture_output=True, text=True, check=True)
    operation_service = json.loads(status.stdout)
    assert operation_service["State"] == "running"
    summary = {"release": str(RELEASE), "previous_release": str(previous), "compatible_rollback": str(COMPAT), "backup": str(BACKUP),
        "linux_tests": counts, "existing_records_preserved": True, "counts": {table: len(ids) for table, ids in after.items()},
        "public_https_ready": True, "schema": "0005_data", "web_version": "stage13-3", "operations_running": True,
        "komari_active": subprocess.run(["systemctl", "is-active", "--quiet", "komari-agent"]).returncode == 0}
    (BACKUP / "release-verification.json").write_text(json.dumps(summary))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
