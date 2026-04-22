from datetime import datetime
from app.extensions import db


class Agent(db.Model):
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        unique=True
    )

    extension = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=False, default='offline')
    sip_username = db.Column(db.String(255), nullable=True)
    sip_password = db.Column(db.String(255), nullable=True)

    last_seen_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    company = db.relationship('Company', back_populates='agents', lazy=True)
    user = db.relationship('User', back_populates='agent_profile', lazy=True)