"""add twilio extended credentials to companies

Revision ID: a3f1e9b2c045
Revises: fe102985df54
Create Date: 2026-04-08 00:00:00.000000

Adiciona twilio_api_key, twilio_api_secret e twilio_twiml_app_sid à tabela
companies para suportar credenciais Twilio por tenant.

- twilio_api_key    : Twilio API Key SID  (para AccessToken do JS SDK)
- twilio_api_secret : Twilio API Secret   (armazenado criptografado com Fernet)
- twilio_twiml_app_sid : SID do TwiML App (roteamento do webphone)
"""
from alembic import op
import sqlalchemy as sa

revision = "a3f1e9b2c045"
down_revision = "fe102985df54"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "companies",
        sa.Column("twilio_api_key", sa.String(255), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("twilio_api_secret", sa.String(512), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("twilio_twiml_app_sid", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("companies", "twilio_twiml_app_sid")
    op.drop_column("companies", "twilio_api_secret")
    op.drop_column("companies", "twilio_api_key")
