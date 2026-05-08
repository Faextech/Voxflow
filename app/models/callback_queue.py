from datetime import datetime
from app import db
from app.core.enums import CallbackStatus


class CallbackQueue(db.Model):
    __tablename__ = "callback_queue"

    id = db.Column(db.Integer, primary_key=True)

    company_id  = db.Column(db.Integer, nullable=True)
    lead_id     = db.Column(db.Integer, nullable=False)
    call_id     = db.Column(db.Integer, nullable=True)
    campaign_id = db.Column(db.Integer, nullable=False)

    # Controle de status
    status = db.Column(
        db.String(50),
        default=CallbackStatus.PENDING.value,
        nullable=False
    )

    # 1=low, 2=medium, 3=high
    priority = db.Column(db.Integer, default=1)

    notes = db.Column(db.Text, nullable=True)

    # Quando deve tentar novamente
    scheduled_for = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Controle de tentativas
    attempts = db.Column(db.Integer, default=0)

    # Operador reservado (se houver)
    reserved_agent_id = db.Column(db.Integer, nullable=True)

    # Controle de tempo
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def to_dict(self):
        from app.models.lead import Lead
        lead = Lead.query.get(self.lead_id) if self.lead_id else None
        return {
            "id":               self.id,
            "company_id":       self.company_id,
            "lead_id":          self.lead_id,
            "lead_name":        lead.name if lead else None,
            "lead_phone":       lead.numero_1 if lead else None,
            "call_id":          self.call_id,
            "campaign_id":      self.campaign_id,
            "status":           self.status,
            "priority":         self.priority or 1,
            "notes":            self.notes,
            "scheduled_for":    self.scheduled_for.isoformat() if self.scheduled_for else None,
            "attempts":         self.attempts,
            "reserved_agent_id": self.reserved_agent_id,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
        }

    def mark_reserved(self, agent_id: int):
        self.status = CallbackStatus.RESERVED.value
        self.reserved_agent_id = agent_id

    def mark_dialing(self):
        self.status = CallbackStatus.DIALING.value
        self.attempts += 1

    def mark_completed(self):
        self.status = CallbackStatus.COMPLETED.value

    def mark_failed(self):
        self.status = CallbackStatus.FAILED.value

    def mark_canceled(self):
        self.status = CallbackStatus.CANCELED.value