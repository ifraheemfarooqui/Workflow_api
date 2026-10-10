"""add verified account deletion support

Revision ID: 6d2ab0e147c9
Revises: 4f8c2d91a6b3
Create Date: 2026-10-09 21:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6d2ab0e147c9"
down_revision: Union[str, Sequence[str], None] = "4f8c2d91a6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    op.alter_column(
        "messages",
        "sender_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "comments",
        "user_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_table(
        "account_deletion_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_account_deletion_codes_id"), "account_deletion_codes", ["id"], unique=False)
    op.create_index(op.f("ix_account_deletion_codes_user_id"), "account_deletion_codes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_account_deletion_codes_user_id"), table_name="account_deletion_codes")
    op.drop_index(op.f("ix_account_deletion_codes_id"), table_name="account_deletion_codes")
    op.drop_table("account_deletion_codes")
    op.alter_column(
        "comments",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "messages",
        "sender_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("users", "is_deleted")
