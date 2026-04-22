from datetime import datetime
from app.extensions import db


class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False
    )

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='draft')
    dial_mode = db.Column(db.String(50), nullable=False, default='manual')
    retry_limit = db.Column(db.Integer, nullable=False, default=3)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    default_pipeline_id = db.Column(
        db.Integer, 
        db.ForeignKey('pipelines.id', ondelete='SET NULL'), 
        nullable=True
    )
    default_stage_id = db.Column(
        db.Integer, 
        db.ForeignKey('pipeline_stages.id', ondelete='SET NULL'), 
        nullable=True
    )

    company = db.relationship('Company', back_populates='campaigns', lazy=True)
    leads = db.relationship('Lead', back_populates='campaign', lazy=True, cascade='all, delete-orphan')
    calls = db.relationship('Call', back_populates='campaign', lazy=True, cascade='all, delete-orphan')
    
    # Filtro: quando True, pula números com padrão de telefone fixo (somente celulares)
    mobile_only = db.Column(db.Boolean, default=False, nullable=False, server_default='0')

    default_pipeline = db.relationship('Pipeline', foreign_keys=[default_pipeline_id])
    default_stage = db.relationship('PipelineStage', foreign_keys=[default_stage_id])