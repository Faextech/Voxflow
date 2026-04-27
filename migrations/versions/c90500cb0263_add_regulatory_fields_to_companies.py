"""add_regulatory_fields_to_companies

Revision ID: c90500cb0263
Revises: 80c547d742c5
Create Date: 2026-04-27 08:43:45.996982

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c90500cb0263'
down_revision = '80c547d742c5'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Use IF NOT EXISTS so this is safe to re-run on PostgreSQL if the migration
    # was previously stamped but not fully applied.
    conn.execute(sa.text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS reg_type VARCHAR(50)"))
    conn.execute(sa.text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS reg_name VARCHAR(255)"))
    conn.execute(sa.text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS reg_tax_id VARCHAR(50)"))
    conn.execute(sa.text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS reg_address TEXT"))
    conn.execute(sa.text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS reg_document_path VARCHAR(512)"))


def downgrade():
    op.drop_column('companies', 'reg_document_path')
    op.drop_column('companies', 'reg_address')
    op.drop_column('companies', 'reg_tax_id')
    op.drop_column('companies', 'reg_name')
    op.drop_column('companies', 'reg_type')
