"""add billing system: credit_balance, cost_per_minute, twilio_subaccount_sid, credit_transactions

Revision ID: d9e5f4a1b832
Revises: c8d4e3f2a105
Create Date: 2026-04-24 00:00:00.000000

Adiciona:
- companies.credit_balance        : saldo em reais do cliente
- companies.cost_per_minute       : custo por minuto de chamada
- companies.twilio_subaccount_sid : SID da subconta Twilio isolada por tenant
- tabela credit_transactions      : histórico de recargas e débitos de chamada
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e5f4a1b832"
down_revision = "c8d4e3f2a105"
branch_labels = None
depends_on = None


def upgrade():
    # Novos campos na tabela companies
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(
            sa.Column("credit_balance", sa.Numeric(12, 4), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("cost_per_minute", sa.Numeric(8, 4), nullable=False, server_default="0.35")
        )
        batch_op.add_column(
            sa.Column("twilio_subaccount_sid", sa.String(255), nullable=True)
        )

    # Nova tabela de transações de crédito
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 4), nullable=False),
        sa.Column("balance_after", sa.Numeric(12, 4), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("call_sid", sa.String(100), nullable=True),
        sa.Column("call_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("payment_id", sa.String(255), nullable=True),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("payment_status", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_credit_transactions_company_id", "credit_transactions", ["company_id"])
    op.create_index("ix_credit_transactions_call_sid", "credit_transactions", ["call_sid"])


def downgrade():
    op.drop_index("ix_credit_transactions_call_sid", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_company_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")

    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_column("twilio_subaccount_sid")
        batch_op.drop_column("cost_per_minute")
        batch_op.drop_column("credit_balance")
