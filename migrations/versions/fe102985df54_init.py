"""init baseline

Revision ID: fe102985df54
Revises:
Create Date: 2026-03-25 08:28:13.546319

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fe102985df54"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Baseline inicial.
    # O banco já foi criado anteriormente com db.create_all(),
    # então esta primeira migration não deve tentar alterar tabelas existentes.
    pass


def downgrade():
    pass