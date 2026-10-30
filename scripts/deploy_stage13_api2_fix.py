"""仅在服务器发布连接探测修复，不混入未完成的B4源码。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path("/srv/model-platform")
RELEASE = ROOT / "releases/20261029-13b3a"
BACKUP = ROOT / "backups/pre-stage13-api2-20261029"


def compose(path):
    return ["docker", "compose", "--env-file", str(path / "deploy/server/.env"), "-f", str(path / "deploy/server/compose.yaml")]


def logged(command, filename):
    with (BACKUP / filename).open("ab") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)


def records(path):
    tables = ("users", "workspaces", "models", "model_versions", "datasets", "dataset_versions", "jobs", "compute_nodes", "annotation_batches", "data_operations")
    sql = "select json_build_object(" + ",".join(f"'{table}',(select coalesce(json_agg(id),'[]') from {table})" for table in tables) + ")"
    result = subprocess.run(compose(path) + ["exec", "-T", "db", "psql", "-U", "postgres", "-d", "model_platform", "-At", "-c", sql], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main():
    assert os.name == "posix" and ROOT.is_dir()
    previous = (ROOT / "current").resolve()
    assert previous.name == "20261029-13b3"
    assert not RELEASE.exists() and not BACKUP.exists()
    BACKUP.mkdir(mode=0o700)
    shutil.copytree(previous, RELEASE)
    changes = {"model_connections.py": "backend/src/model_platform/services/model_connections.py",
               "test_model_connections.py": "backend/tests/test_model_connections.py",
               "events.js": "frontend/live/events.js"}
    for name, destination in changes.items():
        shutil.copy2(ROOT / "staging/api2-fix" / name, RELEASE / destination)
    for path in (RELEASE / "frontend/live").rglob("*"):
        if path.is_file() and path.suffix in {".js", ".html"}:
            path.write_text(path.read_text().replace("stage13-3", "stage13-3a"))
            # 已带3a的events.js来自本机，避免重复添加后缀。
            path.write_text(path.read_text().replace("stage13-3aa", "stage13-3a"))
    env_path = RELEASE / "deploy/server/.env"
    lines = ["RELEASE_ID=" + RELEASE.name if line.startswith("RELEASE_ID=") else line for line in env_path.read_text().splitlines()]
    env_path.write_text("\n".join(lines) + "\n")
    env_path.chmod(0o600)
    migrations = list((RELEASE / "backend/migrations/versions").glob("*.py"))
    assert len(migrations) == 5 and not any("0006" in path.name for path in migrations)
    print("building_connection_fix_on_server", flush=True)
    logged(compose(RELEASE) + ["build", "api"], "build.log")
    print("running_98_isolated_linux_tests", flush=True)
    logged(compose(RELEASE) + ["run", "--rm", "--no-deps", "api", "test", "/app/backend/tests", "-q", "-x", "-o", "cache_dir=/runtime/test-runs/api2-fix-cache", "--basetemp", "/runtime/test-runs/api2-fix", "--junitxml", "/runtime/test-runs/api2-fix.xml"], "tests.log")
    suites = ET.parse(ROOT / "runtime/app/test-runs/api2-fix.xml").getroot().findall("testsuite")
    tests = {key: sum(int(suite.get(key)) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
    assert tests == {"tests": 98, "failures": 0, "errors": 0, "skipped": 0}
    before = records(previous)
    with (BACKUP / "platform.dump").open("xb") as stream:
        subprocess.run(compose(previous) + ["exec", "-T", "db", "pg_dump", "-U", "postgres", "-d", "model_platform", "-Fc"], stdout=stream, check=True)
    (BACKUP / "platform.dump").chmod(0o600)
    shutil.copy2(previous / "deploy/server/.env", BACKUP / "compose.env")
    (BACKUP / "compose.env").chmod(0o600)
    temporary = ROOT / "current-api2-fix"
    assert not temporary.exists() and not temporary.is_symlink()
    temporary.symlink_to(RELEASE)
    temporary.replace(ROOT / "current")
    logged(compose(RELEASE) + ["up", "-d", "--no-deps", "api", "operations"], "activation.log")
    ready = None
    for _ in range(40):
        try:
            with urllib.request.urlopen("http://127.0.0.1:18000/readyz", timeout=2) as response:
                ready = json.load(response)["data"]
            if ready["schema"] == "0005_data":
                break
        except OSError:
            time.sleep(1)
    assert ready and ready["schema"] == "0005_data"
    logged(compose(RELEASE) + ["exec", "-T", "gateway", "nginx", "-s", "reload"], "activation.log")
    with urllib.request.urlopen("https://47.93.115.188:5488/", timeout=10) as response:
        assert "stage13-3a" in response.read().decode()
    print("waiting_for_real_api2_response", flush=True)
    program = '''
import asyncio,json
from sqlalchemy import select
from model_platform.config import Settings
from model_platform.database import make_engine,make_session_factory
from model_platform.models import User
from model_platform.services.model_connections import test_connection
settings=Settings();engine=make_engine(settings.db_url)
async def run():
    with make_session_factory(engine)() as db:
        actor=db.scalar(select(User).where(User.account=='lixu'))
        result=await test_connection(db,settings,actor,'con_d42c51dfa8a74fe6a5a7e78c6b68321b')
        print(json.dumps(result['health']))
try:asyncio.run(run())
finally:engine.dispose()
'''
    command = compose(RELEASE) + ["exec", "-T", "api", "python", "-B", "/app/deploy/server/entrypoint.py", "python", "-"]
    result = subprocess.run(command, input=program, capture_output=True, text=True, check=True)
    health = json.loads(result.stdout)
    assert health["status"] == "available" and "code" not in health, health
    after = records(RELEASE)
    assert all(set(ids) <= set(after[table]) for table, ids in before.items())
    report = {"release": str(RELEASE), "previous_release": str(previous), "backup": str(BACKUP), "schema": "0005_data", "web_version": "stage13-3a",
              "linux_tests": tests, "existing_records_preserved": True, "api2_probe": health, "local_gpu_used": False, "local_services_restarted": False}
    (BACKUP / "verification.json").write_text(json.dumps(report))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
