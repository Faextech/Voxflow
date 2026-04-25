"""
Modelos do Sistema de Suporte (Help Desk)
- SupportTicket  : ticket criado pelo usuário
- TicketMessage  : mensagens dentro de cada ticket (chat)
"""

from datetime import datetime
from app.extensions import db


class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    # Quem abriu o ticket
    created_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    # Responsável pelo atendimento (membro do time de suporte)
    assigned_to = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text,        nullable=False)

    category = db.Column(
        db.String(60),
        nullable=False,
        default='geral'
    )
    # Ex: geral, financeiro, tecnico, comercial, outro

    status = db.Column(
        db.String(30),
        nullable=False,
        default='open',
        index=True,
    )
    # open | in_progress | resolved | closed

    priority = db.Column(
        db.String(20),
        nullable=False,
        default='medium',
        index=True,
    )
    # low | medium | high | urgent

    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at  = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relacionamentos
    messages      = db.relationship(
        'TicketMessage',
        backref='ticket',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='TicketMessage.created_at',
    )
    creator       = db.relationship('User', foreign_keys=[created_by],  lazy='joined')
    assignee      = db.relationship('User', foreign_keys=[assigned_to], lazy='joined')

    # ── Helpers ────────────────────────────────────────────────────────────────

    STATUS_LABELS = {
        'open':        'Aberto',
        'in_progress': 'Em andamento',
        'resolved':    'Resolvido',
        'closed':      'Fechado',
    }

    PRIORITY_LABELS = {
        'low':    'Baixa',
        'medium': 'Média',
        'high':   'Alta',
        'urgent': 'Urgente',
    }

    CATEGORY_LABELS = {
        'geral':      'Geral',
        'financeiro': 'Financeiro',
        'tecnico':    'Técnico',
        'comercial':  'Comercial',
        'outro':      'Outro',
    }

    def to_dict(self, include_messages=False):
        data = {
            'id':          self.id,
            'title':       self.title,
            'description': self.description,
            'category':    self.category,
            'category_label': self.CATEGORY_LABELS.get(self.category, self.category),
            'status':      self.status,
            'status_label': self.STATUS_LABELS.get(self.status, self.status),
            'priority':    self.priority,
            'priority_label': self.PRIORITY_LABELS.get(self.priority, self.priority),
            'created_by':  self.created_by,
            'creator_name': self.creator.name if self.creator else 'Desconhecido',
            'assigned_to': self.assigned_to,
            'assignee_name': self.assignee.name if self.assignee else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at':  self.created_at.isoformat(),
            'updated_at':  self.updated_at.isoformat(),
            'message_count': self.messages.count(),
        }
        if include_messages:
            data['messages'] = [m.to_dict() for m in self.messages]
        return data

    def __repr__(self):
        return f'<SupportTicket id={self.id} status={self.status!r} priority={self.priority!r}>'


class TicketMessage(db.Model):
    __tablename__ = 'ticket_messages'

    id        = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey('support_tickets.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    author_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )

    # 'client' ou 'support'
    author_type = db.Column(db.String(20), nullable=False, default='client')

    body       = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)  # nota interna (só o time vê)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    author = db.relationship('User', foreign_keys=[author_id], lazy='joined')

    def to_dict(self):
        return {
            'id':          self.id,
            'ticket_id':   self.ticket_id,
            'author_id':   self.author_id,
            'author_name': self.author.name if self.author else 'Sistema',
            'author_type': self.author_type,
            'body':        self.body,
            'is_internal': self.is_internal,
            'created_at':  self.created_at.isoformat(),
        }

    def __repr__(self):
        return f'<TicketMessage id={self.id} ticket={self.ticket_id} type={self.author_type!r}>'
