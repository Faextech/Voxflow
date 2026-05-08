"""fix missing columns in calls table (amd_result, amd_recovered, hangup_cause, ringing_at)

Revision ID: f1a2b3c4d5e7
Revises: d1a2b3c4d5e6
Create Date: 2026-04-27 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e7'
down_revision = 'd1a2b3c4d5e6'
branch_labels = None
depends_on = None

_CALLS_COLUMNS = [
    ("amd_result",   "VARCHAR(50)"),
    ("amd_recovered","BOOLEAN DEFAULT FALSE"),
    ("hangup_cause", "VARCHAR(100)"),
    ("ringing_at",   "TIMESTAMP"),
    ("answered_by",  "VARCHAR(50)"),
]


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        for col, col_type in _CALLS_COLUMNS:
            conn.execute(sa.text(
                f"ALTER TABLE calls ADD COLUMN IF NOT EXISTS {col} {col_type}"
            ))
    else:
        existing = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(calls)"))}
        for col, col_type in _CALLS_COLUMNS:
            if col not in existing:
                conn.execute(sa.text(f"ALTER TABLE calls ADD COLUMN {col} {col_type}"))


def downgrade():
    pass
