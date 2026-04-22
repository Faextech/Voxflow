import logging
from datetime import datetime
from app.extensions import db

logger = logging.getLogger(__name__)


class PipelineTransitionRule(db.Model):
    __tablename__ = 'pipeline_transition_rules'

    id                 = db.Column(db.Integer, primary_key=True)
    company_id         = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    source_pipeline_id = db.Column(
        db.Integer,
        db.ForeignKey('pipelines.id', ondelete='CASCADE'),
        nullable=False,
    )
    target_pipeline_id = db.Column(
        db.Integer,
        db.ForeignKey('pipelines.id', ondelete='CASCADE'),
        nullable=False,
    )
    target_stage_id = db.Column(
        db.Integer,
        db.ForeignKey('pipeline_stages.id'),
        nullable=False,
    )
    name           = db.Column(db.String(255), nullable=False)
    is_active      = db.Column(db.Boolean, default=True)
    priority       = db.Column(db.Integer, default=0)
    trigger        = db.Column(db.String(50), nullable=False)
    trigger_config = db.Column(db.JSON, nullable=False, default=dict)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    source_pipeline = db.relationship(
        'Pipeline',
        foreign_keys=[source_pipeline_id],
        back_populates='rules',
    )
    target_pipeline = db.relationship(
        'Pipeline',
        foreign_keys=[target_pipeline_id],
    )
    target_stage = db.relationship(
        'PipelineStage',
        foreign_keys=[target_stage_id],
    )

    def __repr__(self):
        return (
            f'<PipelineTransitionRule id={self.id} '
            f'trigger={self.trigger!r} name={self.name!r}>'
        )
