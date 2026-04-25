"""
Sistema de crédito e billing do NexDial.

Cada Company tem um saldo em reais (credit_balance na tabela companies).
Toda movimentação é registrada em CreditTransaction.
"""

from datetime import datetime
from app.extensions import db


class CreditTransaction(db.Model):
    __tablename__ = "credit_transactions"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "recharge" | "call_debit" | "manual_adjust"
    type = db.Column(db.String(50), nullable=False)

    # Valor positivo = crédito, negativo = débito (em reais)
    amount = db.Column(db.Numeric(12, 4), nullable=False)

    # Saldo após a transação
    balance_after = db.Column(db.Numeric(12, 4), nullable=False)

    # Campos de contexto
    description = db.Column(db.String(512), nullable=True)
    call_sid = db.Column(db.String(100), nullable=True, index=True)
    call_duration_seconds = db.Column(db.Integer, nullable=True)
    payment_id = db.Column(db.String(255), nullable=True)  # ID do gateway de pagamento
    payment_method = db.Column(db.String(50), nullable=True)  # "pix" | "card"
    payment_status = db.Column(db.String(50), nullable=True)  # "pending" | "approved" | "failed"

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    company = db.relationship("Company", back_populates="credit_transactions", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "amount": float(self.amount),
            "balance_after": float(self.balance_after),
            "description": self.description,
            "call_sid": self.call_sid,
            "call_duration_seconds": self.call_duration_seconds,
            "payment_id": self.payment_id,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "created_at": self.created_at.isoformat(),
        }
