"""create initial tables

Revision ID: 001_initial
Revises: 
Create Date: 2025-12-11 22:49:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create channels table
    op.create_table(
        'channels',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('identifier', sa.String(255), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default="active"),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('channel_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('direction', sa.String(10), default="incoming"),
        sa.Column('message_text', sa.Text(), nullable=True),
        sa.Column('ai_response', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(50), default="pending"),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('escalated_to_human', sa.Boolean(), default=False),
        sa.Column('customer_contact', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'])
    )

    # Create knowledge_base table
    op.create_table(
        'knowledge_base',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(50), default="manual"),
        sa.Column('source_link', sa.String(255), nullable=True),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )

    # Create escalations table
    op.create_table(
        'escalations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('message_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('escalated_to', sa.String(255), nullable=False),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.Column('resolved', sa.Boolean(), default=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'])
    )

    # Create analytics table
    op.create_table(
        'analytics',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('total_messages', sa.Integer(), default=0),
        sa.Column('ai_resolved', sa.Integer(), default=0),
        sa.Column('escalated', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )

    # Create voice_messages table
    op.create_table(
        'voice_messages',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('channel_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_contact', sa.String(255), nullable=True),
        sa.Column('transcription', sa.Text(), nullable=True),
        sa.Column('ai_response', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'])
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )

    # Create appointments table
    op.create_table(
        'appointments',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('channel_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('customer_name', sa.String(255), nullable=True),
        sa.Column('customer_contact', sa.String(255), nullable=True),
        sa.Column('service', sa.String(255), nullable=True),
        sa.Column('requested_time', sa.DateTime(), nullable=True),
        sa.Column('confirmed_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(50), default="pending"),
        sa.Column('ai_conversation', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'])
    )

    # Create indexes
    op.create_index('ix_messages_channel_id', 'messages', ['channel_id'])
    op.create_index('ix_escalations_message_id', 'escalations', ['message_id'])
    op.create_index('ix_voice_messages_channel_id', 'voice_messages', ['channel_id'])
    op.create_index('ix_appointments_channel_id', 'appointments', ['channel_id'])


def downgrade():
    # Drop tables in reverse order
    op.drop_table('appointments')
    op.drop_table('users')
    op.drop_table('voice_messages')
    op.drop_table('analytics')
    op.drop_table('escalations')
    op.drop_table('knowledge_base')
    op.drop_table('messages')
    op.drop_table('channels')
