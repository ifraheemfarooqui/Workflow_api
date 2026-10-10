"""add message edit and delete metadata

Revision ID: 1c7a5b9e42d1
Revises: fb66fbeb2cac
Create Date: 2026-10-09 19:57:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1c7a5b9e42d1"
down_revision: Union[str, Sequence[str], None] = "fb66fbeb2cac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("edited_at", sa.DateTime(), nullable=True))
    op.add_column("messages", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "deleted_at")
    op.drop_column("messages", "edited_at")
