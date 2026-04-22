import logging
from datetime import datetime
from app.extensions import db

logger = logging.getLogger(__name__)


class DealActivity(db.Model):
    __tablename__ = 'deal_activities'

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    deal_id    = db.Column(db.Integer, db.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False)
    agent_id   = db.Column(db.Integer, db.ForeignKey('agents.id', ondelete='SET NULL'), nullable=True)

    type  = db.Column(db.String(30), nullable=False)
    # call | note | email | whatsapp | meeting | stage_change | pipeline_transfer | system
    title = db.Column(db.String(255), nullable=True)
    body  = db.Column(db.Text, nullable=True)

    # Stored as 'metadata' in DB; Python attribute is metadata_ to avoid shadowing built-in.
    metadata_ = db.Column('metadata', db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    deal  = db.relationship('Deal', back_populates='activities')
    agent = db.relationship('Agent', foreign_keys=[agent_id])

    def __repr__(self):
        return f'<DealActivity id={self.id} type={self.type!r}>'
