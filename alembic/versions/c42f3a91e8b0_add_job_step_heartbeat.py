"""add job step heartbeat

Revision ID: c42f3a91e8b0
Revises: b6dd8f31c7e2
Create Date: 2026-07-15 14:09:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c42f3a91e8b0"
down_revision: Union[str, None] = "b6dd8f31c7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_steps", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("job_steps", "heartbeat_at")
