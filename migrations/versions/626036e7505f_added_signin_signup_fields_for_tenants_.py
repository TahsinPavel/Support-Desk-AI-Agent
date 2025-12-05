"""added signin/signup fields for tenants, remove user table

Revision ID: 626036e7505f
Revises: 193140746307
Create Date: 2025-12-04 21:01:00.041320

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import uuid
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '626036e7505f'
down_revision: Union[str, Sequence[str], None] = '193140746307'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # First drop foreign key constraints that reference the users table
    # Note: We need to check if these constraints exist before trying to drop them
    
    # Drop constraints on knowledge_base table that might reference users
    op.execute("ALTER TABLE knowledge_base DROP CONSTRAINT IF EXISTS knowledge_base_user_id_fkey")
    op.execute("ALTER TABLE knowledge_base DROP CONSTRAINT IF EXISTS fk_knowledge_base_user")
    
    # Drop constraints on analytics table that might reference users
    op.execute("ALTER TABLE analytics DROP CONSTRAINT IF EXISTS analytics_user_id_fkey")
    op.execute("ALTER TABLE analytics DROP CONSTRAINT IF EXISTS fk_analytics_user")
    
    # Drop the foreign key constraint on tenant_id column (automatically named by PostgreSQL)
    op.execute("ALTER TABLE knowledge_base DROP CONSTRAINT IF EXISTS knowledge_base_tenant_id_fkey")
    op.execute("ALTER TABLE analytics DROP CONSTRAINT IF EXISTS analytics_tenant_id_fkey")
    
    # Drop the users table with cascade to handle any remaining dependencies
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    
    # Create the tenant_auth table
    op.create_table(
        'tenant_auth',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Add missing columns to analytics table
    op.add_column('analytics', sa.Column('period_end', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')))
    op.add_column('analytics', sa.Column('period_type', sa.String(20), nullable=False, server_default='daily'))
    op.add_column('analytics', sa.Column('average_confidence', sa.Float(), nullable=True))
    
    # Add updated_at trigger for tenant_auth
    op.execute("""
        CREATE OR REPLACE FUNCTION update_tenant_auth_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trg_update_tenant_auth_updated_at
        BEFORE UPDATE ON tenant_auth
        FOR EACH ROW
        EXECUTE FUNCTION update_tenant_auth_updated_at();
    """)
    
    # Add updated_at trigger for analytics (update existing trigger)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_analytics_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trg_update_analytics_updated_at
        BEFORE UPDATE ON analytics
        FOR EACH ROW
        EXECUTE FUNCTION update_analytics_updated_at();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tenant_auth triggers
    op.execute("DROP TRIGGER IF EXISTS trg_update_tenant_auth_updated_at ON tenant_auth")
    op.execute("DROP FUNCTION IF EXISTS update_tenant_auth_updated_at()")
    
    # Drop analytics triggers
    op.execute("DROP TRIGGER IF EXISTS trg_update_analytics_updated_at ON analytics")
    op.execute("DROP FUNCTION IF EXISTS update_analytics_updated_at()")
    
    # Drop tenant_auth table
    op.drop_table('tenant_auth')
    
    # Recreate users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('is_admin', sa.Boolean, default=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Add updated_at trigger for users
    op.execute("""
        CREATE OR REPLACE FUNCTION update_users_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trg_update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_users_updated_at();
    """)
    
    # Remove added columns from analytics
    op.drop_column('analytics', 'average_confidence')
    op.drop_column('analytics', 'period_type')
    op.drop_column('analytics', 'period_end')