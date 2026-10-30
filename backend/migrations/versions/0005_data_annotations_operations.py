"""不可变版本来源、人工标注及独立数据操作队列。"""
from alembic import op
import sqlalchemy as sa

revision = "0005_data"
down_revision = "0004_admin"
branch_labels = None
depends_on = None


def upgrade():
    # 旧SQLite库仅增列，避免重建被训练记录引用的版本表。
    op.add_column("dataset_versions", sa.Column("parent_version_id", sa.String(40)))
    op.add_column("dataset_versions", sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table("annotation_batches",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("version_id", sa.String(40), sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("sample_indices", sa.JSON(), nullable=False),
        sa.Column("assigned_to", sa.String(40), sa.ForeignKey("users.id")),
        sa.Column("created_by", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("output_version_id", sa.String(40), sa.ForeignKey("dataset_versions.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False))
    op.create_index("ix_annotation_batches_workspace_id", "annotation_batches", ["workspace_id"])
    op.create_table("annotation_results",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("batch_id", sa.String(40), sa.ForeignKey("annotation_batches.id"), nullable=False),
        sa.Column("sample_index", sa.Integer(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("edited_by", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by", sa.String(40), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint("batch_id", "sample_index"))
    op.create_index("ix_annotation_results_batch_id", "annotation_results", ["batch_id"])
    op.create_table("data_operations",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("version_id", sa.String(40), sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("output_version_ids", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(400), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False))
    op.create_index("ix_data_operations_workspace_id", "data_operations", ["workspace_id"])
    op.create_index("ix_data_operations_status", "data_operations", ["status"])


def downgrade():
    op.drop_table("data_operations")
    op.drop_table("annotation_results")
    op.drop_table("annotation_batches")
    op.drop_column("dataset_versions", "provenance")
    op.drop_column("dataset_versions", "parent_version_id")
