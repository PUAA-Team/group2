"""工作空间训练参数模板。"""
from alembic import op
import sqlalchemy as sa

revision = '0010_templates'
down_revision = '0009_audit'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('training_parameter_templates',
        sa.Column('id', sa.String(40), primary_key=True),
        sa.Column('workspace_id', sa.String(40), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('task_type', sa.String(40), nullable=False),
        sa.Column('trainer_id', sa.String(64), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.String(40), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workspace_id', 'name'))
    op.create_index('ix_training_parameter_templates_workspace_id', 'training_parameter_templates', ['workspace_id'])
    op.create_index('ix_training_parameter_templates_created_at', 'training_parameter_templates', ['created_at'])


def downgrade():
    op.drop_table('training_parameter_templates')
