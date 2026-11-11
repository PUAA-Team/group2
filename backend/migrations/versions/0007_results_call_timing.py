"""评估结果与调用完成时间。"""
from alembic import op
import sqlalchemy as sa

revision = "0007_results"
down_revision = "0006_assist"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("service_calls", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("service_calls", sa.Column("elapsed_ms", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("service_calls", "elapsed_ms")
    op.drop_column("service_calls", "completed_at")
