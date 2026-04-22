import logging
from datetime import datetime
from app.extensions import db

logger = logging.getLogger(__name__)


class DealTask(db.Model):
    __tablename__ = 'deal_tasks'

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    deal_id     = db.Column(db.Integer, db.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('agents.id', ondelete='SET NULL'), nullable=True)

    type        = db.Column(db.String(20), default='call')
    # call | email | whatsapp | meeting | other
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status      = db.Column(db.String(20), default='pending')
    # pending | done | canceled

    due_at     = db.Column(db.DateTime, nullable=True)
    done_at    = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    deal  = db.relationship('Deal', back_populates='tasks')
    agent = db.relationship('Agent', foreign_keys=[assigned_to])

    def __repr__(self):
        return f'<DealTask id={self.id} title={self.title!r} status={self.status!r}>'
