"""失败操作审计的安全元数据。"""
from alembic import op
import sqlalchemy as sa

revision = '0009_audit'
down_revision = '0008_govern'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('audit_events', sa.Column('error_code', sa.String(64), nullable=True))
    op.add_column('audit_events', sa.Column('request_id', sa.String(32), nullable=True))


def downgrade():
    op.drop_column('audit_events', 'request_id')
    op.drop_column('audit_events', 'error_code')
