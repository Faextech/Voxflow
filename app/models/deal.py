import logging
from datetime import datetime
from app.extensions import db

logger = logging.getLogger(__name__)


class Deal(db.Model):
    __tablename__ = 'deals'

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id'), nullable=False)
    stage_id    = db.Column(db.Integer, db.ForeignKey('pipeline_stages.id'), nullable=False)
    lead_id     = db.Column(db.Integer, db.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False)
    agent_id    = db.Column(db.Integer, db.ForeignKey('agents.id', ondelete='SET NULL'), nullable=True)

    title    = db.Column(db.String(255), nullable=False)
    value    = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(3), default='BRL')

    probability = db.Column(db.Integer, nullable=True)
    status      = db.Column(db.String(20), default='open')
    # open | won | lost | frozen | transferred

    notes               = db.Column(db.Text, nullable=True)
    lost_reason         = db.Column(db.String(255), nullable=True)
    expected_close_date = db.Column(db.Date, nullable=True)

    stage_entered_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    won_at           = db.Column(db.DateTime, nullable=True)
    lost_at          = db.Column(db.DateTime, nullable=True)

    pipeline = db.relationship('Pipeline', back_populates='deals')
    stage    = db.relationship('PipelineStage', back_populates='deals', foreign_keys=[stage_id])
    lead     = db.relationship('Lead', foreign_keys=[lead_id])
    agent    = db.relationship('Agent', foreign_keys=[agent_id])

    activities = db.relationship(
        'DealActivity',
        back_populates='deal',
        cascade='all, delete-orphan',
        order_by='DealActivity.created_at.desc()',
    )
    tasks = db.relationship(
        'DealTask',
        back_populates='deal',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<Deal id={self.id} title={self.title!r} status={self.status!r}>'
