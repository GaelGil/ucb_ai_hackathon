"""add datasets table and link data, labels, research

Revision ID: 6711c04595a2
Revises: f40b80b93d9f
Create Date: 2026-06-20 14:25:15.674941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '6711c04595a2'
down_revision: Union[str, Sequence[str], None] = 'f40b80b93d9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # New datasets table (belongs to a language).
    op.create_table(
        'datasets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('language_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['language_id'], ['languages.id'],
            name='fk_datasets_language_id_languages',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_datasets_language_id'), 'datasets', ['language_id'], unique=False)

    # Link data -> datasets (nullable).
    op.add_column('data', sa.Column('dataset_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_data_dataset_id'), 'data', ['dataset_id'], unique=False)
    op.create_foreign_key(
        'fk_data_dataset_id_datasets', 'data', 'datasets', ['dataset_id'], ['id'],
    )

    # Link labels -> datasets (nullable).
    op.add_column('labels', sa.Column('dataset_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_labels_dataset_id'), 'labels', ['dataset_id'], unique=False)
    op.create_foreign_key(
        'fk_labels_dataset_id_datasets', 'labels', 'datasets', ['dataset_id'], ['id'],
    )

    # Link research -> languages (nullable).
    op.add_column('research', sa.Column('language_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_research_language_id'), 'research', ['language_id'], unique=False)
    op.create_foreign_key(
        'fk_research_language_id_languages', 'research', 'languages', ['language_id'], ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_research_language_id_languages', 'research', type_='foreignkey')
    op.drop_index(op.f('ix_research_language_id'), table_name='research')
    op.drop_column('research', 'language_id')

    op.drop_constraint('fk_labels_dataset_id_datasets', 'labels', type_='foreignkey')
    op.drop_index(op.f('ix_labels_dataset_id'), table_name='labels')
    op.drop_column('labels', 'dataset_id')

    op.drop_constraint('fk_data_dataset_id_datasets', 'data', type_='foreignkey')
    op.drop_index(op.f('ix_data_dataset_id'), table_name='data')
    op.drop_column('data', 'dataset_id')

    op.drop_index(op.f('ix_datasets_language_id'), table_name='datasets')
    op.drop_table('datasets')
