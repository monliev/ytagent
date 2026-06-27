"""add_custom_scheduling_fields

Revision ID: d73a4b5e6f21
Revises: a62b3c4d5e6f
Create Date: 2026-06-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd73a4b5e6f21'
down_revision: Union[str, Sequence[str], None] = 'a62b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('channels', sa.Column('upload_days_interval', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('channels', sa.Column('preferred_upload_times', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('channels', 'preferred_upload_times')
    op.drop_column('channels', 'upload_days_interval')
