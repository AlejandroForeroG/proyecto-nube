"""add missing fields in user table

Revision ID: d662dc35ffd0
Revises: 38d52333bf92
Create Date: 2025-10-15 11:42:14.257055

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd662dc35ffd0'
down_revision: Union[str, None] = '38d52333bf92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1) crear como NULL
    op.add_column('users', sa.Column('first_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=255), nullable=True))

    # 2) backfill para filas existentes
    op.execute("UPDATE users SET first_name = '' WHERE first_name IS NULL")
    op.execute("UPDATE users SET last_name = '' WHERE last_name IS NULL")

    # 3) volver NOT NULL
    op.alter_column('users', 'first_name', nullable=False, existing_type=sa.String(length=255))
    op.alter_column('users', 'last_name', nullable=False, existing_type=sa.String(length=255))

def downgrade():
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'last_name')