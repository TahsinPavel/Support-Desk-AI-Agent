"""merge_heads

Revision ID: d520b0df7e92
Revises: 10153d91ae71, 6f7d65545fee
Create Date: 2025-12-07 22:21:01.523631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd520b0df7e92'
down_revision: Union[str, Sequence[str], None] = ('10153d91ae71', '6f7d65545fee')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
