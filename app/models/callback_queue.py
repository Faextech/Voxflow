from datetime import datetime
from app import db
from app.core.enums import CallbackStatus


class CallbackQueue(db.Model):
    __tablename__ = "callback_queue"

    id = db.Column(db.Integer, primary_key=True)

    # Relações principais
    lead_id = db.Column(db.Integer, nullable=False)
    call_id = db.Column(db.Integer, nullable=False)
    campaign_id = db.Column(db.Integer, nullable=False)

    # Controle de status
    status = db.Column(
        db.String(50),
        default=CallbackStatus.PENDING.value,
        nullable=False
    )

    # Prioridade (pode usar depois pra VIP, etc)
    priority = db.Column(db.Integer, default=1)

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
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "call_id": self.call_id,
            "campaign_id": self.campaign_id,
            "status": self.status,
            "priority": self.priority,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "attempts": self.attempts,
            "reserved_agent_id": self.reserved_agent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
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