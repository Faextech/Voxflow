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
    op.add_column('companies', sa.Column('reg_type', sa.String(length=50), nullable=True))
    op.add_column('companies', sa.Column('reg_name', sa.String(length=255), nullable=True))
    op.add_column('companies', sa.Column('reg_tax_id', sa.String(length=50), nullable=True))
    op.add_column('companies', sa.Column('reg_address', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('reg_document_path', sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column('companies', 'reg_document_path')
    op.drop_column('companies', 'reg_address')
    op.drop_column('companies', 'reg_tax_id')
    op.drop_column('companies', 'reg_name')
    op.drop_column('companies', 'reg_type')
