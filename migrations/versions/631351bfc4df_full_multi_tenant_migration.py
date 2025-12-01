"""full_multi_tenant_migration

Revision ID: mt_20251201_full
Revises: 
Create Date: 2025-12-01 01:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = 'mt_20251201_full'
down_revision = 'add_tenants_001'
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------
    # TENANTS: add AI & service fields
    # -------------------------
    op.add_column('tenants', sa.Column('ai_provider', sa.String(50), nullable=True, server_default='openai'))
    op.add_column('tenants', sa.Column('ai_system_prompt', sa.Text, nullable=True))
    op.add_column('tenants', sa.Column('faqs', pg.JSON, nullable=True))
    op.add_column('tenants', sa.Column('services', pg.JSON, nullable=True))
    op.add_column('tenants', sa.Column('escalation_phone', sa.String(50), nullable=True))
    op.add_column('tenants', sa.Column('open_time', sa.String(10), nullable=True))
    op.add_column('tenants', sa.Column('close_time', sa.String(10), nullable=True))

    # -------------------------
    # CHANNELS: add tenant_id & metadata
    # -------------------------
    op.add_column('channels', sa.Column('tenant_id', pg.UUID(as_uuid=True), nullable=True))
    op.add_column('channels', sa.Column('channel_metadata', pg.JSON, nullable=True))
    op.create_foreign_key('fk_channels_tenant', 'channels', 'tenants', ['tenant_id'], ['id'])

    # -------------------------
    # MESSAGES: add tenant_id & metadata
    # -------------------------
    op.add_column('messages', sa.Column('tenant_id', pg.UUID(as_uuid=True), nullable=True))
    op.add_column('messages', sa.Column('message_metadata', pg.JSON, nullable=True))
    op.create_foreign_key('fk_messages_tenant', 'messages', 'tenants', ['tenant_id'], ['id'])

    # -------------------------
    # VOICE_MESSAGES: add tenant_id & metadata
    # -------------------------
    op.add_column('voice_messages', sa.Column('tenant_id', pg.UUID(as_uuid=True), nullable=True))
    op.add_column('voice_messages', sa.Column('voice_metadata', pg.JSON, nullable=True))
    op.create_foreign_key('fk_voice_messages_tenant', 'voice_messages', 'tenants', ['tenant_id'], ['id'])

    # -------------------------
    # ESCALATIONS: add tenant_id
    # -------------------------
    op.add_column('escalations', sa.Column('tenant_id', pg.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_escalations_tenant', 'escalations', 'tenants', ['tenant_id'], ['id'])

    # -------------------------
    # ANALYTICS table
    # -------------------------
    op.create_table(
        'analytics',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', pg.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('period_start', sa.DateTime, default=sa.func.now(), nullable=False),
        sa.Column('total_messages', sa.Integer, default=0, nullable=False),
        sa.Column('ai_resolved', sa.Integer, default=0, nullable=False),
        sa.Column('escalated', sa.Integer, default=0, nullable=False),
        sa.Column('analytics_metadata', pg.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    )


def downgrade():
    # Drop analytics table
    op.drop_table('analytics')

    # Drop tenant-related columns
    op.drop_column('tenants', 'ai_provider')
    op.drop_column('tenants', 'ai_system_prompt')
    op.drop_column('tenants', 'faqs')
    op.drop_column('tenants', 'services')
    op.drop_column('tenants', 'escalation_phone')
    op.drop_column('tenants', 'open_time')
    op.drop_column('tenants', 'close_time')

    # Drop tenant_id & metadata from channels
    op.drop_constraint('fk_channels_tenant', 'channels', type_='foreignkey')
    op.drop_column('channels', 'tenant_id')
    op.drop_column('channels', 'channel_metadata')

    # Drop tenant_id & metadata from messages
    op.drop_constraint('fk_messages_tenant', 'messages', type_='foreignkey')
    op.drop_column('messages', 'tenant_id')
    op.drop_column('messages', 'message_metadata')

    # Drop tenant_id & metadata from voice_messages
    op.drop_constraint('fk_voice_messages_tenant', 'voice_messages', type_='foreignkey')
    op.drop_column('voice_messages', 'tenant_id')
    op.drop_column('voice_messages', 'voice_metadata')

    # Drop tenant_id from escalations
    op.drop_constraint('fk_escalations_tenant', 'escalations', type_='foreignkey')
    op.drop_column('escalations', 'tenant_id')
