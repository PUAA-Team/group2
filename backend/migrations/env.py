from alembic import context

from model_platform.database import Base
from model_platform import models  # noqa: F401
from model_platform import compute_models  # noqa: F401
from model_platform import job_models  # noqa: F401
from model_platform import administration_models  # noqa: F401
from model_platform import data_models  # noqa: F401
from model_platform import assistant_models  # noqa: F401

target_metadata = Base.metadata


def run():
    connection = context.config.attributes.get("connection")
    if connection is None:
        raise RuntimeError("请使用平台 CLI 提供显式数据库连接")
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


run()
