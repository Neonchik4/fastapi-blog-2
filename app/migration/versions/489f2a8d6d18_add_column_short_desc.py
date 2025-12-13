"""Добавление колонки short_description

Revision ID: 489f2a8d6d18
Revises: 0478dbd0f6f6
Create Date: 2024-11-25 10:56:28.040836

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизий, используемые Alembic
revision: str = "489f2a8d6d18"
down_revision: Union[str, None] = "0478dbd0f6f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("blogs", sa.Column("short_description", sa.Text(), nullable=False))


def downgrade() -> None:
    op.drop_constraint(None, "blogs", type_="foreignkey")
    op.create_foreign_key(
        None, "blogs", "users", ["author"], ["id"], ondelete="CASCADE"
    )
    op.drop_column("blogs", "short_description")
