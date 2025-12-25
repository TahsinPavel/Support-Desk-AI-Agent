"""set_default_ai_provider_gemini

Revision ID: 2d4280e5c6cd
Revises: 8ea362d36676
Create Date: 2025-12-25 22:50:11.509999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d4280e5c6cd'
down_revision: Union[str, Sequence[str], None] = '8ea362d36676'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ensure new tenants default to Gemini when ai_provider is omitted.
    op.alter_column(
        'tenants',
        'ai_provider',
        existing_type=sa.String(length=50),
        existing_nullable=True,
        server_default='gemini',
    )

    # Backfill NULL values only (do not overwrite explicitly-set providers).
    op.execute("UPDATE tenants SET ai_provider='gemini' WHERE ai_provider IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'tenants',
        'ai_provider',
        existing_type=sa.String(length=50),
        existing_nullable=True,
        server_default='openai',
    )
