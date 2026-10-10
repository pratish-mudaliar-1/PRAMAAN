"""002_add_centre_coordinates — Add latitude and longitude to Centre.

Revision ID: 002_add_centre_coordinates
Revises: 001_initial_schema
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002_add_centre_coordinates"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("centre", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("centre", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("centre", "longitude")
    op.drop_column("centre", "latitude")
