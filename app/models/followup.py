from datetime import datetime
from app.extensions import db


class FollowUpSequence(db.Model):
    """Defines a reusable follow-up sequence tied to a campaign + call outcome."""
    __tablename__ = "followup_sequences"

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True)

    name        = db.Column(db.String(255), nullable=False)
    # Disposition that triggers enrollment (e.g. "atendeu", "reuniao_agendada", "sem_interesse")
    trigger_disposition = db.Column(db.String(50), nullable=False)
    is_active   = db.Column(db.Boolean, default=True, nullable=False)

    # JSON array: [{delay_minutes: 60, action: "email"|"whatsapp"|"call", template: "..."}]
    steps       = db.Column(db.JSON, nullable=False, default=list)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tasks       = db.relationship("FollowUpTask", back_populates="sequence", lazy=True, cascade="all, delete-orphan")


class FollowUpTask(db.Model):
    """A single scheduled follow-up task for a specific lead."""
    __tablename__ = "followup_tasks"

    id           = db.Column(db.Integer, primary_key=True)
    company_id   = db.Column(db.Integer, nullable=False)
    sequence_id  = db.Column(db.Integer, db.ForeignKey("followup_sequences.id", ondelete="CASCADE"), nullable=False)
    lead_id      = db.Column(db.Integer, db.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    call_id      = db.Column(db.Integer, nullable=True)

    step_index   = db.Column(db.Integer, nullable=False, default=0)
    action       = db.Column(db.String(20), nullable=False)   # email | whatsapp | call
    template     = db.Column(db.Text, nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)

    # pending | sent | skipped | failed
    status       = db.Column(db.String(20), nullable=False, default="pending")
    executed_at  = db.Column(db.DateTime, nullable=True)
    error        = db.Column(db.Text, nullable=True)

    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    sequence = db.relationship("FollowUpSequence", back_populates="tasks")
    lead     = db.relationship("Lead", foreign_keys=[lead_id])
