"""add mobile_only to campaigns

Revision ID: b7c3d2e1f894
Revises: a3f1e9b2c045
Create Date: 2026-04-15 00:00:00.000000

Adiciona coluna mobile_only à tabela campaigns.
Quando True, o discador automático pula números com padrão de telefone fixo
e tenta apenas celulares (números com 9 dígitos locais no padrão BR).
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c3d2e1f894"
down_revision = "a3f1e9b2c045"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c["name"] for c in inspector.get_columns("campaigns")]

    if "mobile_only" not in existing_cols:
        op.add_column(
            "campaigns",
            sa.Column("mobile_only", sa.Boolean(), nullable=False, server_default="0"),
        )


def downgrade():
    op.drop_column("campaigns", "mobile_only")
