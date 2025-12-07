"""remove_support_email_from_tenants

Revision ID: 6f7d65545fee
Revises: d6192da07f72
Create Date: 2025-12-07 22:08:49.009346

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f7d65545fee'
down_revision: Union[str, Sequence[str], None] = 'd6192da07f72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Remove support_email column from tenants table
    op.drop_column('tenants', 'support_email')


def downgrade() -> None:
    """Downgrade schema."""
    # Add support_email column back to tenants table
    op.add_column('tenants', sa.Column('support_email', sa.String(255), nullable=True))
