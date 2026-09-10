"""add question metadata fields

Revision ID: 557f13c4d14f
Revises: d258685ffaaa
Create Date: 2026-09-07 12:30:59.673594

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '557f13c4d14f'
down_revision: Union[str, Sequence[str], None] = 'd258685ffaaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Defined once here so create()/drop() below reference the exact same
# type objects used by the column definitions further down.
difficulty_enum = postgresql.ENUM('EASY', 'MEDIUM', 'HARD', name='question_difficulty')
question_type_enum = postgresql.ENUM('SINGLE_CORRECT', 'MULTIPLE_CORRECT', name='question_type')


def upgrade() -> None:
    """Upgrade schema."""
    # add_column() does NOT reliably auto-create a Postgres enum type on its
    # own — it has to exist before any column can reference it. checkfirst=True
    # makes this safe to re-run without erroring if the type already exists.
    difficulty_enum.create(op.get_bind(), checkfirst=True)
    question_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('questions', sa.Column('topic', sa.String(), server_default='general', nullable=False))
    op.add_column(
        'questions',
        sa.Column('difficulty', difficulty_enum, server_default='MEDIUM', nullable=False),
    )
    op.add_column(
        'questions',
        sa.Column('question_type', question_type_enum, server_default='SINGLE_CORRECT', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Columns must be dropped BEFORE the types they reference, or Postgres
    # will refuse to drop a type that's still in use.
    op.drop_column('questions', 'question_type')
    op.drop_column('questions', 'difficulty')
    op.drop_column('questions', 'topic')

    question_type_enum.drop(op.get_bind(), checkfirst=True)
    difficulty_enum.drop(op.get_bind(), checkfirst=True)