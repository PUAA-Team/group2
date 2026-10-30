import argparse
import getpass
import json
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import Settings
from .database import make_engine, make_session_factory
from .errors import Problem
from .schemas import UserCreate
from .services.identity import initialize_admin


def alembic_config(connection):
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


def migrate(settings):
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.db_url)
    try:
        with engine.begin() as connection:
            command.upgrade(alembic_config(connection), "head")
    finally:
        engine.dispose()


def bootstrap_admin(settings, account, display_name, password):
    payload = UserCreate(account=account, display_name=display_name, password=password, is_admin=True)
    engine = make_engine(settings.db_url)
    try:
        with make_session_factory(engine)() as db:
            try:
                user = initialize_admin(db, payload)
            except Problem as exc:
                if exc.status == 409:
                    raise ValueError(exc.message) from None
                raise
            return user.id
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="训练平台初始化工具")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("migrate")
    admin = sub.add_parser("bootstrap-admin")
    admin.add_argument("--account", required=True)
    admin.add_argument("--display-name", required=True)
    admin.add_argument("--password-stdin", action="store_true")
    export = sub.add_parser("export-openapi")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    if args.action == "migrate":
        migrate(settings)
        print("数据库迁移完成")
    elif args.action == "bootstrap-admin":
        password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("管理员密码（至少12位）: ")
        try:
            bootstrap_admin(settings, args.account, args.display_name, password)
        except ValueError:
            parser.exit(1, "初始化未完成：请检查字段，或确认管理员是否已经存在。\n")
        print("管理员初始化完成")
    elif args.action == "export-openapi":
        from .main import create_app
        app = create_app(settings)
        args.output.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
        app.state.engine.dispose()
        print("OpenAPI 已导出")


if __name__ == "__main__":
    main()
