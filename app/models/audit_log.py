from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id           = db.Column(db.Integer, primary_key=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Actor
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id   = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email   = db.Column(db.String(255), nullable=True)  # snapshot — não muda se email mudar
    ip_address   = db.Column(db.String(45), nullable=True)   # IPv4 ou IPv6

    # Action
    action       = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(50),  nullable=True)
    resource_id  = db.Column(db.Integer,      nullable=True)

    # Payload
    changes      = db.Column(db.JSON, nullable=True)  # {before: {...}, after: {...}}
    status       = db.Column(db.String(20), default="success", nullable=False)  # success | failed
    error        = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<AuditLog {self.action} user={self.user_id} @ {self.created_at}>"
