from datetime import datetime
from app.extensions import db


class DNCEntry(db.Model):
    """Do Not Call list — números que não devem ser discados."""
    __tablename__ = "dnc_entries"
    __table_args__ = (
        db.UniqueConstraint("company_id", "phone_e164", name="uq_dnc_company_phone"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    phone_e164 = db.Column(db.String(30), nullable=False, index=True)
    reason     = db.Column(db.String(100), nullable=True)  # 'user_request' | 'voicemail_limit' | 'manual' etc.
    added_by   = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @classmethod
    def is_blocked(cls, company_id: int, phone: str) -> bool:
        """Retorna True se o número estiver na lista DNC da empresa."""
        normalized = _normalize(phone)
        return cls.query.filter_by(company_id=company_id, phone_e164=normalized).first() is not None

    @classmethod
    def add(cls, company_id: int, phone: str, reason: str = "manual", added_by: int = None):
        """Adiciona número ao DNC (ignora se já existir)."""
        from app.extensions import db as _db
        normalized = _normalize(phone)
        if not cls.query.filter_by(company_id=company_id, phone_e164=normalized).first():
            entry = cls(company_id=company_id, phone_e164=normalized,
                        reason=reason, added_by=added_by)
            _db.session.add(entry)
            _db.session.commit()
        return normalized


def _normalize(phone: str) -> str:
    """Remove caracteres não numéricos, mantém + inicial."""
    if not phone:
        return phone
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    return digits or phone
