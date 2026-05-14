"""add import_order to leads

Revision ID: c8d4e3f2a105
Revises: b7c3d2e1f894
Create Date: 2026-04-16 00:00:00.000000

Adiciona coluna import_order à tabela leads para preservar
a ordem de importação da planilha (de cima para baixo).
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d4e3f2a105"
down_revision = "b7c3d2e1f894"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c["name"] for c in inspector.get_columns("leads")]

    if "import_order" not in existing_cols:
        op.add_column(
            "leads",
            sa.Column("import_order", sa.Integer(), nullable=True),
        )


def downgrade():
    op.drop_column("leads", "import_order")
