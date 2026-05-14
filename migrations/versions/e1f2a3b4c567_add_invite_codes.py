"""add invite_codes table

Revision ID: e1f2a3b4c567
Revises: d9e5f4a1b832
Create Date: 2026-04-26 00:00:00.000000

Adiciona:
- tabela invite_codes: códigos de convite para controle de acesso ao cadastro
"""
from alembic import op
import sqlalchemy as sa


revision = 'e1f2a3b4c567'
down_revision = 'd9e5f4a1b832'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'invite_codes' not in tables:
        op.create_table(
            'invite_codes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(20), nullable=False),
            sa.Column('used', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('used_by_company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=True),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code'),
        )
        op.create_index('ix_invite_codes_code', 'invite_codes', ['code'])


def downgrade():
    op.drop_index('ix_invite_codes_code', table_name='invite_codes')
    op.drop_table('invite_codes')
