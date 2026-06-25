"""add_preset_templates_and_template_id

Revision ID: 8d72118ffea0
Revises: c51a7b8e92d0
Create Date: 2026-06-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d72118ffea0'
down_revision: Union[str, Sequence[str], None] = 'c51a7b8e92d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('channels', sa.Column('preset_templates', sa.JSON(), nullable=True))
    op.add_column('videos', sa.Column('metadata_template_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('channels', 'preset_templates')
    op.drop_column('videos', 'metadata_template_id')
