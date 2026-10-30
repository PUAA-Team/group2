"""平台设置、外部模型连接和单次邀请。"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0004_admin"
down_revision = "0003_jobs"
branch_labels = None
depends_on = None


def upgrade():
    settings = op.create_table("platform_settings",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False))
    op.bulk_insert(settings, [{"id": "platform", "value": {"platform_name": "模训平台", "invitations_enabled": True, "max_upload_mib": 10, "max_samples": 10000, "global_concurrent_jobs": 16}, "created_at": datetime.now(timezone.utc), "revision": 1}])
    op.create_table("model_connections",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("endpoint", sa.String(1000), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("secret_ref", sa.String(80)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("health", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False))
    op.create_table("user_invitations",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("group_id", sa.String(40), sa.ForeignKey("user_groups.id")),
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("used_by", sa.String(40), sa.ForeignKey("users.id")),
        sa.Column("created_by", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("user_invitations")
    op.drop_table("model_connections")
    op.drop_table("platform_settings")
