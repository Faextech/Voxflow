from datetime import datetime
from app.extensions import db


class Call(db.Model):
    __tablename__ = 'calls'

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False
    )

    campaign_id = db.Column(
        db.Integer,
        db.ForeignKey('campaigns.id', ondelete='CASCADE'),
        nullable=False
    )

    lead_id = db.Column(
        db.Integer,
        db.ForeignKey('leads.id', ondelete='CASCADE'),
        nullable=False
    )

    agent_id = db.Column(
        db.Integer,
        db.ForeignKey('agents.id', ondelete='SET NULL'),
        nullable=True
    )

    phone_dialed = db.Column(db.String(30), nullable=False)
    call_sid = db.Column(db.String(255), unique=True, index=True, nullable=True)

    direction = db.Column(db.String(50), nullable=False, default='outbound')
    status = db.Column(db.String(50), nullable=False, default='queued')

    answered_by = db.Column(db.String(50), nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=False, default=0)
    attempt = db.Column(db.Integer, nullable=False, default=1)

    recording_url = db.Column(db.Text, nullable=True)
    disposition = db.Column(db.String(100), nullable=True)
    amd_result = db.Column(db.String(50), nullable=True)   # human | machine_start | unknown | timeout
    amd_recovered = db.Column(db.Boolean, default=False)   # True se supervisor reclassificou
    hangup_cause = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ringing_at = db.Column(db.DateTime, nullable=True)
    answered_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    company = db.relationship('Company', back_populates='calls', lazy=True)
    campaign = db.relationship('Campaign', back_populates='calls', lazy=True)
    lead = db.relationship('Lead', back_populates='calls', lazy=True)
    agent = db.relationship('Agent', backref='calls', lazy=True)