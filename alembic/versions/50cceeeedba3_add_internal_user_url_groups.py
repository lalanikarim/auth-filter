"""add internal user/url groups

Revision ID: 50cceeeedba3
Revises: 05c98e3f8e3c
Create Date: 2025-07-17 07:56:36.407034

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50cceeeedba3'
down_revision: Union[str, Sequence[str], None] = '05c98e3f8e3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Insert Internal User Group
    op.execute("""
        INSERT INTO user_groups (name, protected, created_at)
        SELECT 'Internal User Group', 1, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM user_groups WHERE name='Internal User Group');
    """)
    # Insert Everyone Url Group
    op.execute("""
        INSERT INTO url_groups (name, protected, created_at)
        SELECT 'Everyone', 1, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM url_groups WHERE name='Everyone');
    """)
    # Insert Authenticated Url Group
    op.execute("""
        INSERT INTO url_groups (name, protected, created_at)
        SELECT 'Authenticated', 1, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM url_groups WHERE name='Authenticated');
    """)


def downgrade() -> None:
    op.execute("DELETE FROM user_groups WHERE name='Internal User Group' AND protected=1;")
    op.execute("DELETE FROM url_groups WHERE name IN ('Everyone', 'Authenticated') AND protected=1;")
