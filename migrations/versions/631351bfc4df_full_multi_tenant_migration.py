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
    # TENANTS: add AI & service fields (skip those already added by previous migration)
    # -------------------------
    # These columns were already added by add_multi_tenant_architecture migration:
    # ai_provider, ai_system_prompt, faqs, services, escalation_phone, open_time, close_time
    
    # -------------------------
    # CHANNELS: add metadata (tenant_id already added)
    # -------------------------
    op.add_column('channels', sa.Column('channel_metadata', pg.JSON, nullable=True))
    # Foreign key already created by previous migration
    
    # -------------------------
    # MESSAGES: add metadata (tenant_id already added)
    # -------------------------
    op.add_column('messages', sa.Column('message_metadata', pg.JSON, nullable=True))
    # Foreign key already created by previous migration
    
    # -------------------------
    # VOICE_MESSAGES: add metadata (tenant_id already added)
    # -------------------------
    op.add_column('voice_messages', sa.Column('voice_metadata', pg.JSON, nullable=True))
    # Foreign key already created by previous migration
    
    # -------------------------
    # ESCALATIONS: tenant_id already added
    # -------------------------
    # Foreign key already created by previous migration
    
    # -------------------------
    # ANALYTICS table (already created by initial migration, add metadata)
    # -------------------------
    op.add_column('analytics', sa.Column('analytics_metadata', pg.JSON, nullable=True))


def downgrade():
    # Drop metadata columns only (since other columns were added by previous migration)
    op.drop_column('analytics', 'analytics_metadata')
    op.drop_column('channels', 'channel_metadata')
    op.drop_column('messages', 'message_metadata')
    op.drop_column('voice_messages', 'voice_metadata')
    
    # Note: tenant_id columns and foreign keys are handled by the previous migration's downgrade
