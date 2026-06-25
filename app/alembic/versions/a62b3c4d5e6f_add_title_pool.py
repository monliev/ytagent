"""add_title_pool

Revision ID: a62b3c4d5e6f
Revises: 8d72118ffea0
Create Date: 2026-06-25 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a62b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = '8d72118ffea0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('channels', sa.Column('title_pool', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('channels', 'title_pool')
