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
    op.create_table(
        'appointments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('channel_id', UUID(as_uuid=True), sa.ForeignKey('channels.id'), nullable=True),
        sa.Column('customer_name', sa.String(255), nullable=True),
        sa.Column('customer_contact', sa.String(255), nullable=True),
        sa.Column('service', sa.String(255), nullable=True),
        sa.Column('requested_time', sa.DateTime(), nullable=True),
        sa.Column('confirmed_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('ai_conversation', sa.JSON, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'))
    )

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
    op.execute("DROP TRIGGER IF EXISTS trg_update_appointments_updated_at ON appointments")
    op.execute("DROP FUNCTION IF EXISTS update_appointments_updated_at()")
    op.drop_table('appointments')
