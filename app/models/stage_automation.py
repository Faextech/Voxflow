import logging
from datetime import datetime
from app.extensions import db

logger = logging.getLogger(__name__)


class StageAutomation(db.Model):
    __tablename__ = 'stage_automations'

    id         = db.Column(db.Integer, primary_key=True)
    stage_id   = db.Column(db.Integer, db.ForeignKey('pipeline_stages.id', ondelete='CASCADE'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    is_active  = db.Column(db.Boolean, default=True)
    position   = db.Column(db.Integer, default=0)
    type       = db.Column(db.String(30), nullable=False)
    config     = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stage = db.relationship('PipelineStage', back_populates='automations')

    def __repr__(self):
        return f'<StageAutomation id={self.id} type={self.type!r}>'


class AutomationLog(db.Model):
    __tablename__ = 'automation_logs'

    id            = db.Column(db.Integer, primary_key=True)
    company_id    = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    automation_id = db.Column(
        db.Integer,
        db.ForeignKey('stage_automations.id', ondelete='SET NULL'),
        nullable=True,
    )
    deal_id = db.Column(
        db.Integer,
        db.ForeignKey('deals.id', ondelete='SET NULL'),
        nullable=True,
    )
    lead_id = db.Column(
        db.Integer,
        db.ForeignKey('leads.id', ondelete='SET NULL'),
        nullable=True,
    )
    type          = db.Column(db.String(30))
    status        = db.Column(db.String(20))   # 'success' | 'failed' | 'skipped'
    error_message = db.Column(db.Text, nullable=True)
    executed_at   = db.Column(db.DateTime, default=datetime.utcnow)
    payload       = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f'<AutomationLog id={self.id} status={self.status!r}>'
