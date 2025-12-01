"""sync_models

Revision ID: 7d53661cc15e
Revises: mt_20251201_full
Create Date: 2025-12-01 23:08:24.376458

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '7d53661cc15e'
down_revision: Union[str, Sequence[str], None] = 'mt_20251201_full'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)

    # -------------------------
    # TENANTS TABLE
    # -------------------------
    if 'tenants' not in insp.get_table_names():
        op.create_table(
            'tenants',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('primary_phone', sa.String(length=50), nullable=True, unique=True),
            sa.Column('support_email', sa.String(length=255), nullable=True),
            sa.Column('timezone', sa.String(length=50), default='UTC'),
            sa.Column('open_time', sa.String(length=10), nullable=True),
            sa.Column('close_time', sa.String(length=10), nullable=True),
            sa.Column('ai_provider', sa.String(length=50), nullable=True, server_default='openai'),
            sa.Column('ai_system_prompt', sa.Text, nullable=True),
            sa.Column('faqs', sa.JSON, nullable=True),
            sa.Column('services', sa.JSON, nullable=True),
            sa.Column('escalation_phone', sa.String(length=50), nullable=True),
            sa.Column('is_active', sa.Boolean, default=True),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
        )
    else:
        columns = [c['name'] for c in insp.get_columns('tenants')]
        if 'ai_provider' not in columns:
            op.add_column('tenants', sa.Column('ai_provider', sa.String(50), nullable=True, server_default='openai'))
        if 'ai_system_prompt' not in columns:
            op.add_column('tenants', sa.Column('ai_system_prompt', sa.Text, nullable=True))
        if 'faqs' not in columns:
            op.add_column('tenants', sa.Column('faqs', sa.JSON, nullable=True))
        if 'services' not in columns:
            op.add_column('tenants', sa.Column('services', sa.JSON, nullable=True))
        if 'escalation_phone' not in columns:
            op.add_column('tenants', sa.Column('escalation_phone', sa.String(50), nullable=True))

    # -------------------------
    # CHANNELS TABLE
    # -------------------------
    if 'channels' not in insp.get_table_names():
        op.create_table(
            'channels',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False),
            sa.Column('identifier', sa.String(length=255), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=50), default='active'),
            sa.Column('channel_metadata', sa.JSON, nullable=True),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
            sa.UniqueConstraint('tenant_id', 'type', 'identifier', name='uq_tenant_type_identifier')
        )
    else:
        columns = [c['name'] for c in insp.get_columns('channels')]
        if 'description' not in columns:
            op.add_column('channels', sa.Column('description', sa.String(255), nullable=True))
        if 'channel_metadata' not in columns:
            op.add_column('channels', sa.Column('channel_metadata', sa.JSON, nullable=True))

    # -------------------------
    # MESSAGES TABLE
    # -------------------------
    if 'messages' not in insp.get_table_names():
        op.create_table(
            'messages',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('channel_id', sa.String(length=36), sa.ForeignKey('channels.id'), nullable=False),
            sa.Column('session_id', sa.String(255), nullable=True),
            sa.Column('from_contact', sa.String(255), nullable=True),
            sa.Column('to_contact', sa.String(255), nullable=True),
            sa.Column('direction', sa.String(10), default='incoming'),
            sa.Column('message_text', sa.Text, nullable=True),
            sa.Column('ai_response', sa.Text, nullable=True),
            sa.Column('confidence_score', sa.Float, nullable=True),
            sa.Column('provider', sa.String(50), nullable=True),
            sa.Column('message_metadata', sa.JSON, nullable=True),
            sa.Column('sms_metadata', sa.JSON, nullable=True),
            sa.Column('status', sa.String(50), default='pending'),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
        )
    else:
        columns = [c['name'] for c in insp.get_columns('messages')]
        if 'message_metadata' not in columns:
            op.add_column('messages', sa.Column('message_metadata', sa.JSON, nullable=True))
        if 'sms_metadata' not in columns:
            op.add_column('messages', sa.Column('sms_metadata', sa.JSON, nullable=True))

    # -------------------------
    # VOICE MESSAGES TABLE
    # -------------------------
    if 'voice_messages' not in insp.get_table_names():
        op.create_table(
            'voice_messages',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('message_id', sa.String(length=36), sa.ForeignKey('messages.id'), nullable=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('channel_id', sa.String(length=36), sa.ForeignKey('channels.id'), nullable=False),
            sa.Column('from_contact', sa.String(255), nullable=True),
            sa.Column('transcription', sa.Text, nullable=True),
            sa.Column('ai_response', sa.Text, nullable=True),
            sa.Column('confidence_score', sa.Float, nullable=True),
            sa.Column('voice_metadata', sa.JSON, nullable=True),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
        )
    else:
        columns = [c['name'] for c in insp.get_columns('voice_messages')]
        if 'voice_metadata' not in columns:
            op.add_column('voice_messages', sa.Column('voice_metadata', sa.JSON, nullable=True))

    # -------------------------
    # USERS TABLE
    # -------------------------
    if 'users' not in insp.get_table_names():
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=True),
            sa.Column('email', sa.String(length=255), unique=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=True),
            sa.Column('phone', sa.String(length=50), nullable=True),
            sa.Column('hashed_password', sa.String(length=255), nullable=True),
            sa.Column('is_admin', sa.Boolean, default=False),
            sa.Column('is_active', sa.Boolean, default=True),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
        )

def downgrade():
    # Optional: implement downgrade logic if necessary
    pass