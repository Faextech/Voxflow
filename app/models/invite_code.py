from datetime import datetime

from app.extensions import db


class InviteCode(db.Model):
    __tablename__ = "invite_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_by_company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    def is_valid(self):
        if self.used:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
