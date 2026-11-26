"""账号维度登录限流滑动窗口。

设计选择（dev-plan 19B-3）：在原有“账号+IP”单桶限流之外，
新增纯账号维度的全局滑动失败计数。攻击者轮换 IP 也无法绕过：
同一账号在滑动窗口内累计失败达到阈值即锁定整个账号。
login_attempts 表新增 window_started_at，记录当前滑动窗口的
起始时间；窗口过期后计数归零重新累计。

SQLite 与 PostgreSQL 均为简单加列，无需重建表。
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_login_account_limit'
down_revision = '0014_worker_credential'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("login_attempts",
                  sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("login_attempts", "window_started_at")
