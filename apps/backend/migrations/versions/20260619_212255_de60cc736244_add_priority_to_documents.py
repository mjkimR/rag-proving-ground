"""add priority to documents

Revision ID: de60cc736244
Revises: 85044fa49f6c
Create Date: 2026-06-19 21:22:55.145583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de60cc736244'
down_revision: Union[str, None] = '85044fa49f6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('knowledge_base_documents', sa.Column('priority', sa.String(), nullable=False, server_default='medium'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('knowledge_base_documents', 'priority')
