"""add job step item progress

Revision ID: 8d36d8b334a1
Revises: 2b58c77800bf
Create Date: 2026-07-15 13:24:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d36d8b334a1"
down_revision: Union[str, None] = "2b58c77800bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_steps", sa.Column("items_total", sa.Integer(), nullable=True))
    op.add_column("job_steps", sa.Column("items_completed", sa.Integer(), server_default="0", nullable=False))
    op.add_column("job_steps", sa.Column("items_succeeded", sa.Integer(), server_default="0", nullable=False))
    op.add_column("job_steps", sa.Column("items_failed", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("job_steps", "items_failed")
    op.drop_column("job_steps", "items_succeeded")
    op.drop_column("job_steps", "items_completed")
    op.drop_column("job_steps", "items_total")
