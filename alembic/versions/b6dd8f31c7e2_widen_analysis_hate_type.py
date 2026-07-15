"""widen analysis hate type

Revision ID: b6dd8f31c7e2
Revises: 8d36d8b334a1
Create Date: 2026-07-15 13:31:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6dd8f31c7e2"
down_revision: Union[str, None] = "8d36d8b334a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("comment_analysis_results") as batch_op:
        batch_op.alter_column("hate_type", existing_type=sa.String(length=64), type_=sa.Text())
    with op.batch_alter_table("script_analysis_results") as batch_op:
        batch_op.alter_column("hate_type", existing_type=sa.String(length=64), type_=sa.Text())


def downgrade() -> None:
    with op.batch_alter_table("script_analysis_results") as batch_op:
        batch_op.alter_column("hate_type", existing_type=sa.Text(), type_=sa.String(length=64))
    with op.batch_alter_table("comment_analysis_results") as batch_op:
        batch_op.alter_column("hate_type", existing_type=sa.Text(), type_=sa.String(length=64))
