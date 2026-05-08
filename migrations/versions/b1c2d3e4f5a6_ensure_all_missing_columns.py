"""Ensure all missing columns that were handled by _auto_add_missing_columns

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-08 00:00:00.000000

Migration idempotente que garante todas as colunas cobertas pelo antigo
_auto_add_missing_columns (removido neste sprint).
Usa IF NOT EXISTS no Postgres e pragma_table_info no SQLite.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def _add_if_missing(conn, dialect, table, col, col_type):
    if dialect == "postgresql":
        conn.execute(sa.text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
        ))
    else:
        rows = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        existing = {row[1] for row in rows}
        if col not in existing:
            conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    companies = [
        ("credit_balance",        "NUMERIC(12, 4) DEFAULT 0"),
        ("cost_per_minute",       "NUMERIC(8, 4) DEFAULT 0.35"),
        ("twilio_subaccount_sid", "VARCHAR(255)"),
        ("reg_type",              "VARCHAR(50)"),
        ("reg_name",              "VARCHAR(255)"),
        ("reg_tax_id",            "VARCHAR(50)"),
        ("reg_address",           "TEXT"),
        ("reg_document_path",     "VARCHAR(512)"),
        ("phone",                 "VARCHAR(50)"),
        ("segment",               "VARCHAR(100)"),
    ]
    for col, col_type in companies:
        _add_if_missing(conn, dialect, "companies", col, col_type)

    leads = [
        ("city",  "VARCHAR(100)"),
        ("state", "VARCHAR(50)"),
    ]
    for col, col_type in leads:
        _add_if_missing(conn, dialect, "leads", col, col_type)

    campaigns = [
        ("default_pipeline_id",       "INTEGER"),
        ("default_stage_id",          "INTEGER"),
        ("ring_timeout_seconds",      "INTEGER DEFAULT 50"),
        ("amd_duration_threshold_ms", "INTEGER DEFAULT 6000"),
        ("allowed_hours_start",       "INTEGER DEFAULT 8"),
        ("allowed_hours_end",         "INTEGER DEFAULT 20"),
        ("allowed_timezone",          "VARCHAR(50) DEFAULT 'America/Sao_Paulo'"),
        ("allowed_weekdays",          "VARCHAR(20) DEFAULT '1,2,3,4,5'"),
        ("unknown_amd_action",        "VARCHAR(20) DEFAULT 'send_to_agent'"),
        ("caller_id_pool",            "TEXT"),
        ("caller_id_index",           "INTEGER DEFAULT 0"),
        ("call_script",               "TEXT"),
        ("predictive_ratio",          "REAL DEFAULT 1.5"),
    ]
    for col, col_type in campaigns:
        _add_if_missing(conn, dialect, "campaigns", col, col_type)

    users = [
        ("totp_secret",  "VARCHAR(64)"),
        ("totp_enabled", "BOOLEAN DEFAULT FALSE"),
    ]
    for col, col_type in users:
        _add_if_missing(conn, dialect, "users", col, col_type)

    _add_if_missing(conn, dialect, "deals", "notes", "TEXT")

    callback_queue = [
        ("company_id", "INTEGER"),
        ("notes",      "TEXT"),
    ]
    for col, col_type in callback_queue:
        _add_if_missing(conn, dialect, "callback_queue", col, col_type)


def downgrade():
    pass
