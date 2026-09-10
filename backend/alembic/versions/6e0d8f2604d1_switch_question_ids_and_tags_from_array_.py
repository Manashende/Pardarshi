"""switch question_ids and tags from ARRAY to JSON for portability

Revision ID: 6e0d8f2604d1
Revises: 9f482f8d83b2
Create Date: 2026-08-28 16:30:43.728345

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6e0d8f2604d1'
down_revision: Union[str, Sequence[str], None] = '9f482f8d83b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('paper_variants', 'question_ids')
    op.add_column('paper_variants', sa.Column('question_ids', sa.JSON(), nullable=False, server_default='[]'))
    op.alter_column('paper_variants', 'question_ids', server_default=None)

    op.drop_column('questions', 'tags')
    op.add_column('questions', sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'))
    op.alter_column('questions', 'tags', server_default=None)
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_column('questions', 'tags')
    op.add_column('questions', sa.Column('tags', postgresql.ARRAY(sa.VARCHAR()), nullable=False))

    op.drop_column('paper_variants', 'question_ids')
    op.add_column('paper_variants', sa.Column('question_ids', postgresql.ARRAY(sa.UUID()), nullable=False))
    # ### end Alembic commands ###
