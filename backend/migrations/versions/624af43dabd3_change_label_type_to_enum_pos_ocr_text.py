"""change label.type to enum (pos, ocr, text)

Revision ID: 624af43dabd3
Revises: 5e519a099282
Create Date: 2026-06-20 13:52:15.806611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '624af43dabd3'
down_revision: Union[str, Sequence[str], None] = '5e519a099282'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

labeltype = postgresql.ENUM('pos', 'ocr', 'text', name='labeltype')


def upgrade() -> None:
    """Upgrade schema: convert labels.type from VARCHAR to the labeltype enum."""
    bind = op.get_bind()
    labeltype.create(bind, checkfirst=True)
    op.alter_column(
        'labels',
        'type',
        existing_type=sa.VARCHAR(),
        type_=labeltype,
        existing_nullable=False,
        postgresql_using='type::labeltype',
    )


def downgrade() -> None:
    """Downgrade schema: convert labels.type back to VARCHAR and drop the enum."""
    op.alter_column(
        'labels',
        'type',
        existing_type=labeltype,
        type_=sa.VARCHAR(),
        existing_nullable=False,
        postgresql_using='type::text',
    )
    labeltype.drop(op.get_bind(), checkfirst=True)
