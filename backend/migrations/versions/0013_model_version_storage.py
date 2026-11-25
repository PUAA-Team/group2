"""受控模型权重版本存储字段。"""
from alembic import op
import sqlalchemy as sa

revision = '0013_model_storage'
down_revision = '0012_workspace'
branch_labels = None
depends_on = None


def upgrade():
    mode = 'always' if op.get_bind().dialect.name == 'sqlite' else 'auto'
    with op.batch_alter_table('model_versions', recreate=mode) as batch:
        batch.add_column(sa.Column('storage_key', sa.String(200), nullable=True))
        batch.add_column(sa.Column('sha256', sa.String(64), nullable=True))
        batch.add_column(sa.Column('size_bytes', sa.Integer(), nullable=True))
        batch.create_unique_constraint('uq_model_versions_storage_key', ['storage_key'])


def downgrade():
    with op.batch_alter_table('model_versions') as batch:
        batch.drop_constraint('uq_model_versions_storage_key', type_='unique')
        batch.drop_column('size_bytes')
        batch.drop_column('sha256')
        batch.drop_column('storage_key')
