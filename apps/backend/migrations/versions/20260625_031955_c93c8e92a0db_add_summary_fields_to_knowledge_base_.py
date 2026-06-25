"""Add summary fields to knowledge_base_documents

Revision ID: c93c8e92a0db
Revises: a5847a34ac23
Create Date: 2026-06-25 03:19:55.497698

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c93c8e92a0db'
down_revision: Union[str, None] = 'a5847a34ac23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('knowledge_base_documents', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('knowledge_base_documents', sa.Column('summary_model', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('knowledge_base_documents', 'summary_model')
    op.drop_column('knowledge_base_documents', 'summary')
