"""Add is_pinned to messages and channel_bookmarks table

Revision ID: 0003_pins_and_bookmarks
Revises: 0002_workspace_members_audit
Create Date: 2026-10-14 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003_pins_and_bookmarks'
down_revision: Union[str, None] = '0002_workspace_members_audit'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Add is_pinned to messages
    if 'messages' in tables:
        columns = [c['name'] for c in inspector.get_columns('messages')]
        if 'is_pinned' not in columns:
            op.add_column('messages', sa.Column('is_pinned', sa.Boolean(), server_default=sa.false(), nullable=False))

    # 2. Create channel_bookmarks table
    if 'channel_bookmarks' not in tables:
        op.create_table(
            'channel_bookmarks',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('channel_id', sa.String(length=36), sa.ForeignKey('channels.id'), nullable=False),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id'), nullable=False),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('url', sa.String(length=512), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table('channel_bookmarks')
    op.drop_column('messages', 'is_pinned')
