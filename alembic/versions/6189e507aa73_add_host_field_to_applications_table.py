"""add host field to applications table

Revision ID: 6189e507aa73
Revises: c8a33a2d50ab
Create Date: 2025-07-18 19:28:06.140578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6189e507aa73'
down_revision: Union[str, Sequence[str], None] = 'c8a33a2d50ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('applications', sa.Column('host', sa.String(length=255), nullable=False))
    op.drop_index(op.f('name'), table_name='applications')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('name'), 'applications', ['name'], unique=True)
    op.drop_column('applications', 'host')
    # ### end Alembic commands ###
