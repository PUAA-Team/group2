"""工作空间邀请链接与审核加入申请。"""
from alembic import op
import sqlalchemy as sa

revision = '0012_workspace'
down_revision = '0011_console'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'workspace_invites',
        sa.Column('id', sa.String(40), primary_key=True),
        sa.Column('workspace_id', sa.String(40), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('code_digest', sa.String(64), nullable=False, unique=True),
        sa.Column('code_preview', sa.String(16), nullable=False),
        sa.Column('role', sa.String(10), nullable=False),
        sa.Column('require_approval', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(40), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index('ix_workspace_invites_workspace_id', 'workspace_invites', ['workspace_id'])

    op.create_table(
        'workspace_join_requests',
        sa.Column('id', sa.String(40), primary_key=True),
        sa.Column('workspace_id', sa.String(40), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('invite_id', sa.String(40), sa.ForeignKey('workspace_invites.id'), nullable=False),
        sa.Column('user_id', sa.String(40), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('requested_role', sa.String(10), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', sa.String(40), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('workspace_id', 'user_id', 'invite_id'),
    )
    op.create_index('ix_workspace_join_requests_workspace_id', 'workspace_join_requests', ['workspace_id'])
    op.create_index('ix_workspace_join_requests_user_id', 'workspace_join_requests', ['user_id'])
    op.create_index('ix_workspace_join_requests_status', 'workspace_join_requests', ['status'])


def downgrade():
    op.drop_index('ix_workspace_join_requests_status', table_name='workspace_join_requests')
    op.drop_index('ix_workspace_join_requests_user_id', table_name='workspace_join_requests')
    op.drop_index('ix_workspace_join_requests_workspace_id', table_name='workspace_join_requests')
    op.drop_table('workspace_join_requests')
    op.drop_index('ix_workspace_invites_workspace_id', table_name='workspace_invites')
    op.drop_table('workspace_invites')
