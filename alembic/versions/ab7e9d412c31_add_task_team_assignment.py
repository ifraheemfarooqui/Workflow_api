"""add task team assignment

Revision ID: ab7e9d412c31
Revises: 6d2ab0e147c9
Create Date: 2026-10-10 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab7e9d412c31"
down_revision: Union[str, Sequence[str], None] = "6d2ab0e147c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("assigned_team_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_assigned_team_id_teams",
        "tasks",
        "teams",
        ["assigned_team_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_assigned_team_id_teams", "tasks", type_="foreignkey")
    op.drop_column("tasks", "assigned_team_id")
