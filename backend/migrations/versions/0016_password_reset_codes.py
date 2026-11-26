"""一次性密码重置码表（dev-plan 20A-1）。

管理员签发一次性密码重置码，用户凭码在登录页自助重置密码：
- 明文码只在签发响应里返回一次，库里只存 HMAC-SHA-256 摘要；
- 码默认 15 分钟过期（MT_PASSWORD_RESET_CODE_MINUTES 可配），一次有效；
- 重置成功后自动踢出该用户全部历史会话并清除登录限流计数。

注意：dev-plan 原文写的是迁移 0014，但 0014（Worker 凭据轮换）与
0015（登录限流）已存在，本迁移顺延为 0016。

SQLite 与 PostgreSQL 均为新建表，无需重建已有表。
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_password_reset'
down_revision = '0015_login_account_limit'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "password_reset_codes",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_password_reset_codes_user_id", "password_reset_codes", ["user_id"])
    op.create_index("ix_password_reset_codes_expires_at", "password_reset_codes", ["expires_at"])


def downgrade():
    op.drop_index("ix_password_reset_codes_expires_at", table_name="password_reset_codes")
    op.drop_index("ix_password_reset_codes_user_id", table_name="password_reset_codes")
    op.drop_table("password_reset_codes")
