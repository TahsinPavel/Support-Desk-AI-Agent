"""add_google_oauth_fields_to_tenants

Revision ID: 3b4f1c2d9a01
Revises: 2d4280e5c6cd
Create Date: 2025-12-28

"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "3b4f1c2d9a01"
down_revision: Union[str, Sequence[str], None] = "2d4280e5c6cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add provider field (default local)
    op.add_column(
        "tenants",
        sa.Column("auth_provider", sa.String(length=50), nullable=True, server_default="local"),
    )
    op.execute("UPDATE tenants SET auth_provider='local' WHERE auth_provider IS NULL")
    op.alter_column("tenants", "auth_provider", existing_type=sa.String(length=50), nullable=False)

    # Add Google subject (sub) for stable account linking
    op.add_column(
        "tenants",
        sa.Column("google_sub", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_tenants_google_sub", "tenants", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenants_google_sub", table_name="tenants")
    op.drop_column("tenants", "google_sub")
    op.drop_column("tenants", "auth_provider")
