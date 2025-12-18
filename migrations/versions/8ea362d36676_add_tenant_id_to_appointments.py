"""add_tenant_id_to_appointments

Revision ID: 8ea362d36676
Revises: business_name_fix
Create Date: 2025-12-18 20:52:00.634338

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8ea362d36676'
down_revision: Union[str, Sequence[str], None] = 'business_name_fix'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "appointments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        """
        UPDATE appointments AS a
        SET tenant_id = c.tenant_id
        FROM channels AS c
        WHERE a.channel_id = c.id
          AND a.tenant_id IS NULL
        """
    )

    op.alter_column("appointments", "tenant_id", nullable=False)

    op.create_foreign_key(
        "fk_appointments_tenant_id_tenants",
        "appointments",
        "tenants",
        ["tenant_id"],
        ["id"],
    )

    op.create_index("ix_appointments_tenant_id", "appointments", ["tenant_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_appointments_tenant_id", table_name="appointments")
    op.drop_constraint(
        "fk_appointments_tenant_id_tenants",
        "appointments",
        type_="foreignkey",
    )
    op.drop_column("appointments", "tenant_id")
