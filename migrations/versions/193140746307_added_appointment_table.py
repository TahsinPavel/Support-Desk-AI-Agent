"""Added appointment table

Revision ID: 193140746307
Revises: 2cf5772b3ff7
Create Date: 2025-12-02 23:26:47.629667

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import uuid
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '193140746307'
down_revision: Union[str, Sequence[str], None] = '2cf5772b3ff7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # appointments table already created by initial migration
    # Just add the trigger for auto-updating updated_at
    
    # Auto-update updated_at on row update
    op.execute("""
        CREATE OR REPLACE FUNCTION update_appointments_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_update_appointments_updated_at
        BEFORE UPDATE ON appointments
        FOR EACH ROW
        EXECUTE FUNCTION update_appointments_updated_at();
    """)


def downgrade():
    # Just drop the trigger and function (table will be dropped by initial migration's downgrade)
    op.execute("DROP TRIGGER IF EXISTS trg_update_appointments_updated_at ON appointments")
    op.execute("DROP FUNCTION IF EXISTS update_appointments_updated_at()")
