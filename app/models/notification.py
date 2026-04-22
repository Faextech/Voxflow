import logging
from datetime import datetime
from app.extensions import db

logger = logging.getLogger(__name__)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    agent_id   = db.Column(db.Integer, db.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False)
    deal_id    = db.Column(
        db.Integer,
        db.ForeignKey('deals.id', ondelete='SET NULL'),
        nullable=True,
    )

    type    = db.Column(db.String(30))
    # stage_entry | task_due | pipeline_transfer | mention
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification id={self.id} type={self.type!r} is_read={self.is_read}>'
