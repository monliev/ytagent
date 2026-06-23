"""add_settings_and_gcp_json

Revision ID: f7823ab921c5
Revises: b622304ffbc9
Create Date: 2026-06-23 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7823ab921c5'
down_revision: Union[str, Sequence[str], None] = 'b622304ffbc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create system_settings table
    op.create_table('system_settings',
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('value', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_system_settings_key'), 'system_settings', ['key'], unique=False)

    # Add client_secret_json to gcp_projects
    op.add_column('gcp_projects', sa.Column('client_secret_json', sa.Text(), nullable=True))

    # Alter client_secret_path to be nullable
    op.alter_column('gcp_projects', 'client_secret_path',
               existing_type=sa.String(length=256),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Alter client_secret_path to be NOT nullable
    op.alter_column('gcp_projects', 'client_secret_path',
               existing_type=sa.String(length=256),
               nullable=False)

    # Drop client_secret_json
    op.drop_column('gcp_projects', 'client_secret_json')

    # Drop system_settings
    op.drop_index(op.f('ix_system_settings_key'), table_name='system_settings')
    op.drop_table('system_settings')
