"""空间授权、固定输入确认、智能请求及人工采纳。"""
from alembic import op
import sqlalchemy as sa

revision = "0006_assist"
down_revision = "0005_data"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("workspace_ai_policies",
        sa.Column("id", sa.String(40), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False))
    op.create_table("assistant_requests",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("created_by", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("connection_id", sa.String(40), sa.ForeignKey("model_connections.id"), nullable=False),
        sa.Column("connection_revision", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("preview", sa.JSON(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("error", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False))
    for column in ("workspace_id", "created_by", "confirmed_at", "status"):
        op.create_index("ix_assistant_requests_" + column, "assistant_requests", [column])
    op.create_table("assistant_adoptions",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("request_id", sa.String(40), sa.ForeignKey("assistant_requests.id"), nullable=False, unique=True),
        sa.Column("actor_id", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column("annotation_results", sa.Column("edits", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("annotation_results", sa.Column("origin", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("annotation_results", "origin")
    op.drop_column("annotation_results", "edits")
    op.drop_table("assistant_adoptions")
    op.drop_table("assistant_requests")
    op.drop_table("workspace_ai_policies")
