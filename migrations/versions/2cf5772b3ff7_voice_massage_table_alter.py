"""Voice massage table alter

Revision ID: 2cf5772b3ff7
Revises: 7d53661cc15e
Create Date: 2025-12-02 14:42:34.179398

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import uuid
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '2cf5772b3ff7'
down_revision: Union[str, Sequence[str], None] = '7d53661cc15e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'voice_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('channel_id', UUID(as_uuid=True), sa.ForeignKey('channels.id'), nullable=False),
        sa.Column('from_contact', sa.String(255), nullable=True),
        sa.Column('transcription', sa.Text, nullable=True),
        sa.Column('ai_response', sa.Text, nullable=True),
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'))
    )

    # Auto-update updated_at on row update
    op.execute("""
        CREATE OR REPLACE FUNCTION update_voice_messages_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_update_voice_messages_updated_at
        BEFORE UPDATE ON voice_messages
        FOR EACH ROW
        EXECUTE FUNCTION update_voice_messages_updated_at();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_update_voice_messages_updated_at ON voice_messages")
    op.execute("DROP FUNCTION IF EXISTS update_voice_messages_updated_at()")
    op.drop_table('voice_messages')