"""add check constraint on messages target

Revision ID: fb66fbeb2cac
Revises: f3dce68162e1
Create Date: 2026-10-03 19:01:58.402139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb66fbeb2cac'
down_revision: Union[str, Sequence[str], None] = 'f3dce68162e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_messages_exactly_one_target",
        "messages",
        "(team_id IS NOT NULL) <> (recipient_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_messages_exactly_one_target", "messages", type_="check")

