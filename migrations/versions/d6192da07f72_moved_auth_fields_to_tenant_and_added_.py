"""moved_auth_fields_to_tenant_and_added_subscription_fields

Revision ID: d6192da07f72
Revises: 626036e7505f
Create Date: 2025-12-04 21:10:26.936957

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import uuid
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'd6192da07f72'
down_revision: Union[str, Sequence[str], None] = '626036e7505f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the tenant_auth table
    op.drop_table('tenant_auth')
    
    # Add new columns to tenants table for authentication (allowing NULL initially)
    op.add_column('tenants', sa.Column('owner_name', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('hashed_password', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('business_name', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('plan', sa.String(50), server_default='starter'))
    op.add_column('tenants', sa.Column('subscription_status', sa.String(50), server_default='active'))
    op.add_column('tenants', sa.Column('paddle_customer_id', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('paddle_subscription_id', sa.String(255), nullable=True))
    
    # Remove name column from tenants (replaced by business_name)
    op.drop_column('tenants', 'name')
    
    # Remove period_end, period_type, and average_confidence from analytics (not in new model)
    op.drop_column('analytics', 'period_end')
    op.drop_column('analytics', 'period_type')
    op.drop_column('analytics', 'average_confidence')


def downgrade() -> None:
    """Downgrade schema."""
    # Add back the tenant_auth table
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
    
    # Remove authentication columns from tenants
    op.drop_column('tenants', 'owner_name')
    op.drop_column('tenants', 'email')
    op.drop_column('tenants', 'hashed_password')
    op.drop_column('tenants', 'business_name')
    op.drop_column('tenants', 'plan')
    op.drop_column('tenants', 'subscription_status')
    op.drop_column('tenants', 'paddle_customer_id')
    op.drop_column('tenants', 'paddle_subscription_id')
    
    # Add back name column to tenants
    op.add_column('tenants', sa.Column('name', sa.String(255), nullable=False))
    
    # Add back period_end, period_type, and average_confidence to analytics
    op.add_column('analytics', sa.Column('period_end', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')))
    op.add_column('analytics', sa.Column('period_type', sa.String(20), nullable=False, server_default='daily'))
    op.add_column('analytics', sa.Column('average_confidence', sa.Float(), nullable=True))