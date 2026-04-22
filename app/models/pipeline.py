import logging
from datetime import datetime
from app.extensions import db

logger = logging.getLogger(__name__)


class Pipeline(db.Model):
    __tablename__ = 'pipelines'

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    name        = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    color       = db.Column(db.String(7), default='#6366f1')
    icon        = db.Column(db.String(50), nullable=True)
    position    = db.Column(db.Integer, default=0)
    is_default  = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stages = db.relationship(
        'PipelineStage',
        back_populates='pipeline',
        order_by='PipelineStage.position',
        cascade='all, delete-orphan',
    )
    deals = db.relationship('Deal', back_populates='pipeline', lazy='dynamic')
    rules = db.relationship(
        'PipelineTransitionRule',
        foreign_keys='PipelineTransitionRule.source_pipeline_id',
        back_populates='source_pipeline',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<Pipeline id={self.id} name={self.name!r}>'


class PipelineStage(db.Model):
    __tablename__ = 'pipeline_stages'

    id          = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id', ondelete='CASCADE'), nullable=False)
    company_id  = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    name        = db.Column(db.String(255), nullable=False)
    position    = db.Column(db.Integer, nullable=False, default=0)
    color       = db.Column(db.String(7), default='#6366f1')
    is_won      = db.Column(db.Boolean, default=False)
    is_lost     = db.Column(db.Boolean, default=False)
    is_meeting  = db.Column(db.Boolean, default=False)
    default_probability = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    pipeline    = db.relationship('Pipeline', back_populates='stages')
    deals       = db.relationship('Deal', back_populates='stage', lazy='dynamic')
    automations = db.relationship(
        'StageAutomation',
        back_populates='stage',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<PipelineStage id={self.id} name={self.name!r}>'
