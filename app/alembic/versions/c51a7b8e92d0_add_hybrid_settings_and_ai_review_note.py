"""add_hybrid_settings_and_ai_review_note

Revision ID: c51a7b8e92d0
Revises: f7823ab921c5
Create Date: 2026-06-24 21:18:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c51a7b8e92d0'
down_revision: Union[str, Sequence[str], None] = 'f7823ab921c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Alter channels table
    op.add_column('channels', sa.Column('playlist_id', sa.String(length=64), nullable=True))
    op.add_column('channels', sa.Column('default_language', sa.String(length=16), nullable=True))
    op.add_column('channels', sa.Column('age_restricted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('channels', sa.Column('ai_generated', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('channels', sa.Column('category_id', sa.String(length=16), nullable=True))

    # Alter videos table
    op.add_column('videos', sa.Column('playlist_id', sa.String(length=64), nullable=True))
    op.add_column('videos', sa.Column('default_language', sa.String(length=16), nullable=True))
    op.add_column('videos', sa.Column('age_restricted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('videos', sa.Column('ai_generated', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('videos', sa.Column('category_id', sa.String(length=16), nullable=False, server_default='10'))
    op.add_column('videos', sa.Column('made_for_kids', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('videos', sa.Column('ai_review_note', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Revert channels table changes
    op.drop_column('channels', 'playlist_id')
    op.drop_column('channels', 'default_language')
    op.drop_column('channels', 'age_restricted')
    op.drop_column('channels', 'ai_generated')
    op.drop_column('channels', 'category_id')

    # Revert videos table changes
    op.drop_column('videos', 'playlist_id')
    op.drop_column('videos', 'default_language')
    op.drop_column('videos', 'age_restricted')
    op.drop_column('videos', 'ai_generated')
    op.drop_column('videos', 'category_id')
    op.drop_column('videos', 'made_for_kids')
    op.drop_column('videos', 'ai_review_note')
