"""fix_business_name_only

Revision ID: business_name_fix
Revises: d520b0df7e92
Create Date: 2025-12-13 21:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'business_name_fix'
down_revision: Union[str, Sequence[str], None] = 'd520b0df7e92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - only fix business_name nullable constraint."""
    # Update any NULL business_name values to a default first
    op.execute("UPDATE tenants SET business_name = 'Default Business Name' WHERE business_name IS NULL")
    
    # Then make the column NOT NULL
    op.alter_column('tenants', 'business_name',
                   existing_type=sa.VARCHAR(length=255),
                   nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('tenants', 'business_name',
                   existing_type=sa.VARCHAR(length=255),
                   nullable=True)
