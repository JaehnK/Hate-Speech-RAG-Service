"""move report export storage to db

Revision ID: 4faa97fd166a
Revises: e7a4c10d4f82
Create Date: 2026-07-19 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4faa97fd166a"
down_revision: Union[str, None] = "e7a4c10d4f82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("report_exports", sa.Column("file_blob", sa.LargeBinary(), nullable=True))
    op.drop_column("report_exports", "file_uri")


def downgrade() -> None:
    op.add_column("report_exports", sa.Column("file_uri", sa.Text(), nullable=True))
    op.drop_column("report_exports", "file_blob")
