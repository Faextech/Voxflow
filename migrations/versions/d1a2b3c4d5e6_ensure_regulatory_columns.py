"""ensure_regulatory_columns

Revision ID: d1a2b3c4d5e6
Revises: c90500cb0263
Create Date: 2026-04-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd1a2b3c4d5e6'
down_revision = 'c90500cb0263'
branch_labels = None
depends_on = None


_COLUMNS = [
    ("reg_type",          "VARCHAR(50)"),
    ("reg_name",          "VARCHAR(255)"),
    ("reg_tax_id",        "VARCHAR(50)"),
    ("reg_address",       "TEXT"),
    ("reg_document_path", "VARCHAR(512)"),
]


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        for col, col_type in _COLUMNS:
            conn.execute(sa.text(
                f"ALTER TABLE companies ADD COLUMN IF NOT EXISTS {col} {col_type}"
            ))
    else:
        # SQLite: check existing columns before adding
        existing = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(companies)"))}
        for col, col_type in _COLUMNS:
            if col not in existing:
                conn.execute(sa.text(f"ALTER TABLE companies ADD COLUMN {col} {col_type}"))


def downgrade():
    pass
