"""add_onboarding_completed_to_tenants

Revision ID: 10153d91ae71
Revises: 7d53661cc15e
Create Date: 2025-12-07 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10153d91ae71'
down_revision: Union[str, Sequence[str], None] = '7d53661cc15e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add onboarding_completed column to tenants table
    op.add_column('tenants', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove onboarding_completed column from tenants table
    op.drop_column('tenants', 'onboarding_completed')