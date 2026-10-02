"""remove role system

Revision ID: 5ffb1c397840
Revises: f0267f5578b6
Create Date: 2026-10-02 16:33:20.406097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '5ffb1c397840'
down_revision: Union[str, Sequence[str], None] = 'f0267f5578b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f('users_ibfk_1'), 'users', type_='foreignkey')
    op.drop_column('users', 'role_id')
    op.drop_table('roles')


def downgrade() -> None:
    op.create_table('roles',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('name', mysql.VARCHAR(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index(op.f('ix_roles_id'), 'roles', ['id'], unique=False)
    op.create_index('name', 'roles', ['name'], unique=True)
    op.add_column('users', sa.Column('role_id', mysql.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(op.f('users_ibfk_1'), 'users', 'roles', ['role_id'], ['id'])