import importlib.util
from pathlib import Path
import sys

import pytest


def test_container_tests_do_not_inherit_application_database(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[2] / "deploy/server/entrypoint.py"
    spec = importlib.util.spec_from_file_location("container_entrypoint", path)
    entrypoint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entrypoint)
    monkeypatch.setenv("MT_DATABASE_URL", "postgresql+psycopg://private-production-database")
    monkeypatch.setenv("MT_DATABASE_PASSWORD", "private-production-password")
    monkeypatch.setenv("MT_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("MT_SECURE_COOKIE", "1")
    monkeypatch.setenv("MT_ALLOWED_ORIGINS", "https://private-production-origin")
    monkeypatch.setattr(sys, "argv", [str(path), "test", "-q"])

    def forbidden_configuration():
        pytest.fail("测试不得配置应用数据库")

    class ReplacedProcess(Exception):
        pass

    def execute(executable, arguments):
        assert "MT_DATABASE_URL" not in entrypoint.os.environ
        assert "MT_DATABASE_PASSWORD" not in entrypoint.os.environ
        assert "MT_SECURE_COOKIE" not in entrypoint.os.environ
        assert "MT_ALLOWED_ORIGINS" not in entrypoint.os.environ
        assert Path(entrypoint.os.environ["MT_RUNTIME_DIR"]).is_relative_to(tmp_path / "test-runs")
        assert arguments[2:4] == ["-m", "pytest"]
        raise ReplacedProcess

    monkeypatch.setattr(entrypoint, "configure_database", forbidden_configuration)
    monkeypatch.setattr(entrypoint.os, "execv", execute)
    with pytest.raises(ReplacedProcess):
        entrypoint.main()
