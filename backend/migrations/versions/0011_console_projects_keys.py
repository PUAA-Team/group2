"""项目生命周期及可追溯密钥调用；原调用不猜测来源。"""
from alembic import op
import sqlalchemy as sa

revision = '0011_console'
down_revision = '0010_templates'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('training_projects', sa.Column('description', sa.Text(), nullable=False, server_default=''))
    op.add_column('training_projects', sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()))
    # SQLite以重建表接纳CURRENT_TIMESTAMP默认值，保留原密钥及调用行。
    mode = 'always' if op.get_bind().dialect.name == 'sqlite' else 'auto'
    with op.batch_alter_table('service_keys', recreate=mode) as batch:
        batch.add_column(sa.Column('revision', sa.Integer(), nullable=False, server_default='1'))
        batch.add_column(sa.Column('usage_started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()))
    with op.batch_alter_table('service_calls', recreate=mode) as batch:
        batch.add_column(sa.Column('service_key_id', sa.String(40), nullable=True))
        batch.create_foreign_key('fk_service_calls_service_key_id', 'service_keys', ['service_key_id'], ['id'])
        batch.create_index('ix_service_calls_service_key_id', ['service_key_id'])


def downgrade():
    with op.batch_alter_table('service_calls') as batch:
        batch.drop_index('ix_service_calls_service_key_id')
        batch.drop_constraint('fk_service_calls_service_key_id', type_='foreignkey')
        batch.drop_column('service_key_id')
    with op.batch_alter_table('service_keys') as batch:
        batch.drop_column('usage_started_at')
        batch.drop_column('revision')
    with op.batch_alter_table('training_projects') as batch:
        batch.drop_column('archived')
        batch.drop_column('description')
