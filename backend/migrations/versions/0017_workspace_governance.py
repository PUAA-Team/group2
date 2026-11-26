"""空间自治与团队治理：成员空间子配额与空间总预算（Stage 21A）。"""
from alembic import op
import sqlalchemy as sa

revision = "0017_workspace_governance"
down_revision = "0016_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("memberships", sa.Column("quota", sa.JSON(), nullable=True))
    op.create_table(
        "workspace_budgets",
        sa.Column("id", sa.String(length=40), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_workspace_budgets_created_at", "workspace_budgets", ["created_at"])


def downgrade():
    op.drop_index("ix_workspace_budgets_created_at", table_name="workspace_budgets")
    op.drop_table("workspace_budgets")
    op.drop_column("memberships", "quota")
