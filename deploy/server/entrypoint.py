"""容器启动时组合数据库连接，凭据不进入进程参数或启动输出。"""
import os
from pathlib import Path
import sys
from urllib.parse import quote
from uuid import uuid4


def configure_database():
    password = os.environ.pop("MT_DATABASE_PASSWORD", None)
    if not password:
        raise ValueError("缺少应用数据库凭据")
    host = os.environ.get("MT_DATABASE_HOST", "db")
    user = os.environ.get("MT_DATABASE_USER", "model_platform")
    database = os.environ.get("MT_DATABASE_NAME", "model_platform")
    os.environ["MT_DATABASE_URL"] = (
        f"postgresql+psycopg://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}:5432/{quote(database, safe='')}"
    )
    runtime = Path(os.environ["MT_RUNTIME_DIR"])
    for relative in ("temp", "storage", "bundles", "logs"):
        (runtime / relative).mkdir(parents=True, exist_ok=True)


def main():
    arguments = sys.argv[1:] or ["serve"]
    if arguments[0] == "test":
        # 独立测试只使用fixture创建的临时数据库，不继承正式连接。
        runtime = Path(os.environ["MT_RUNTIME_DIR"]) / "test-runs" / uuid4().hex
        (runtime / "temp").mkdir(parents=True)
        for key in ("MT_DATABASE_URL", "MT_DATABASE_PASSWORD", "MT_ALLOWED_ORIGINS",
                    "MT_SECURE_COOKIE", "MT_ALLOW_BROWSER_SETUP", "MT_ENABLE_LOCAL_WORKER"):
            os.environ.pop(key, None)
        os.environ["MT_RUNTIME_DIR"] = str(runtime)
        os.environ["TMPDIR"] = str(runtime / "temp")
        command = [sys.executable, "-B", "-m", "pytest", *arguments[1:]]
        os.execv(command[0], command)
        return
    configure_database()
    if arguments[0] == "serve":
        command = [sys.executable, "-B", "-m", "uvicorn", "model_platform.main:create_app",
                   "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1",
                   "--no-access-log", "--no-proxy-headers"]
    elif arguments[0] in {"migrate", "cli"}:
        cli_arguments = ["migrate"] if arguments[0] == "migrate" else arguments[1:]
        command = [sys.executable, "-B", "-m", "model_platform.cli", *cli_arguments]
    elif arguments[0] == "python":
        command = [sys.executable, "-B", *arguments[1:]]
    elif arguments[0] == "operations":
        command = [sys.executable, "-B", "-m", "model_platform.operations_runner"]
    else:
        raise ValueError("未知容器操作")
    os.execv(command[0], command)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        # 不把连接串、凭据或环境变量展开到容器日志。
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        sys.exit("启动未完成：" + message)
