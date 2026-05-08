"""add segment column to companies

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e7
Create Date: 2026-05-07 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS segment VARCHAR(100)"
        ))
    else:
        existing = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(companies)"))}
        if "segment" not in existing:
            conn.execute(sa.text("ALTER TABLE companies ADD COLUMN segment VARCHAR(100)"))


def downgrade():
    pass
