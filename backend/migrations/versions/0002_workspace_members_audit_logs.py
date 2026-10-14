"""Add workspace_members, channel_members, and audit_logs tables

Revision ID: 0002_workspace_members_audit_logs
Revises: 0001_initial_schema
Create Date: 2026-10-13 22:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0002_workspace_members_audit_logs'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. workspace_members table
    if 'workspace_members' not in tables:
        op.create_table(
            'workspace_members',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id'), nullable=False),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('role', sa.String(length=32), nullable=False, server_default='member'),
            sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_members_workspace_user'),
        )

    # 2. channel_members table
    if 'channel_members' not in tables:
        op.create_table(
            'channel_members',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('channel_id', sa.String(length=36), sa.ForeignKey('channels.id'), nullable=False),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('role', sa.String(length=32), nullable=False, server_default='member'),
            sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('channel_id', 'user_id', name='uq_channel_members_channel_user'),
        )

    # 3. audit_logs table
    if 'audit_logs' not in tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id'), nullable=False),
            sa.Column('actor_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('action', sa.String(length=64), nullable=False),
            sa.Column('target_id', sa.String(length=64), nullable=True),
            sa.Column('details', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('channel_members')
    op.drop_table('workspace_members')
