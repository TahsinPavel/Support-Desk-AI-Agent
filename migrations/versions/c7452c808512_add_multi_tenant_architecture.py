"""add multi-tenant architecture

Revision ID: c7452c808512
Revises: 
Create Date: 2025-12-01 13:43:45.404330

"""
from alembic import op
import sqlalchemy as sa
import uuid

# Replace with your previous migration ID
revision = 'add_tenants_001'
down_revision = '001_initial'  # This depends on the initial tables
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('primary_phone', sa.String(50), unique=True),
        sa.Column('support_email', sa.String(255)),
        sa.Column('timezone', sa.String(50), server_default="UTC"),
        sa.Column('open_time', sa.String(10)),
        sa.Column('close_time', sa.String(10)),
        sa.Column('ai_provider', sa.String(50), server_default="openai"),
        sa.Column('ai_system_prompt', sa.Text()),
        sa.Column('faqs', sa.JSON()),
        sa.Column('services', sa.JSON()),
        sa.Column('escalation_phone', sa.String(50)),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text("true")),

        sa.Column('created_at', sa.DateTime(), server_default=sa.text("now()")),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text("now()"))
    )

    # 2. Insert default tenant for old data
    op.execute("""
        INSERT INTO tenants (id, name, timezone, is_active)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Default Tenant', 'UTC', true)
    """)

    # 3. Add tenant_id columns to existing tables
    tables_to_update = [
        "channels",
        "messages",
        "knowledge_base",
        "escalations",
        "analytics",
        "users"
    ]

    for table in tables_to_update:
        op.add_column(
            table,
            sa.Column(
                'tenant_id',
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tenants.id"),
                nullable=True
            )
        )

    # 4. Backfill existing rows (assign everything to Default Tenant)
    for table in tables_to_update:
        op.execute(f"""
            UPDATE {table}
            SET tenant_id = '00000000-0000-0000-0000-000000000001'
            WHERE tenant_id IS NULL
        """)

    # 5. Make tenant_id NOT NULL
    for table in tables_to_update:
        op.alter_column(
            table,
            'tenant_id',
            nullable=False
        )

    # 6. Add necessary indexes
    op.create_index('ix_channels_tenant_id', 'channels', ['tenant_id'])
    op.create_index('ix_messages_tenant_id', 'messages', ['tenant_id'])
    op.create_index('ix_kb_tenant_id', 'knowledge_base', ['tenant_id'])
    op.create_index('ix_escalations_tenant_id', 'escalations', ['tenant_id'])
    op.create_index('ix_analytics_tenant_id', 'analytics', ['tenant_id'])
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])


def downgrade():

    tables = ["users", "analytics", "escalations", "knowledge_base", "messages", "channels"]

    # Remove FKs and columns
    for table in tables:
        op.drop_index(f'ix_{table}_tenant_id', table_name=table)
        op.drop_column(table, 'tenant_id')

    # Remove tenant table
    op.drop_table('tenants')

