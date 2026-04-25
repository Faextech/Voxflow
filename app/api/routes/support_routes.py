"""
API do Sistema de Suporte (Help Desk)
Prefixo: /api/support

Endpoints:
  GET    /api/support/tickets              – lista tickets do tenant (com filtros)
  POST   /api/support/tickets              – cria novo ticket
  GET    /api/support/tickets/<id>         – detalhe do ticket + mensagens
  PATCH  /api/support/tickets/<id>         – atualiza status/prioridade/responsável
  DELETE /api/support/tickets/<id>         – remove ticket (admin only)

  POST   /api/support/tickets/<id>/messages        – envia mensagem no ticket
  GET    /api/support/tickets/<id>/messages        – lista mensagens

  GET    /api/support/stats                – estatísticas (admin)
  GET    /api/support/agents               – lista usuários disponíveis para atribuição
"""

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.auth import require_auth, require_role
from app.extensions import db
from app.models.support import SupportTicket, TicketMessage
from app.models.user import User

logger = logging.getLogger(__name__)

support_bp = Blueprint('support', __name__, url_prefix='/api/support')


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

VALID_STATUSES   = {'open', 'in_progress', 'resolved', 'closed'}
VALID_PRIORITIES = {'low', 'medium', 'high', 'urgent'}
VALID_CATEGORIES = {'geral', 'financeiro', 'tecnico', 'comercial', 'outro'}


def _ticket_or_404(ticket_id: int):
    """Busca ticket. Se for system_admin, busca sem filtro de company, caso contrário filtra pelo tenant."""
    is_sys_admin = (g.company_id == 1 and g.user_role in ('admin', 'supervisor'))
    
    q = SupportTicket.query.filter_by(id=ticket_id)
    if not is_sys_admin:
        q = q.filter_by(company_id=g.company_id)
        
    return q.first()


# ─────────────────────────────────────────────────────────────────────────────
# TICKETS – listagem e criação
# ─────────────────────────────────────────────────────────────────────────────

@support_bp.route('/tickets', methods=['GET'])
@require_auth
def list_tickets():
    """
    Lista tickets.
    - Admins veem todos os tickets da empresa.
    - Agentes comuns veem apenas os próprios tickets (created_by == g.user_id).

    Query params:
      status     – open | in_progress | resolved | closed
      priority   – low | medium | high | urgent
      category   – geral | financeiro | tecnico | comercial | outro
      assigned_to – user_id (admin)
      search     – texto livre no título
      page       – default 1
      per_page   – default 20, max 100
      sort       – created_at | updated_at | priority | status (default created_at)
      order      – asc | desc (default desc)
    """
    is_sys_admin = (g.company_id == 1 and g.user_role in ('admin', 'supervisor'))

    if is_sys_admin:
        q = SupportTicket.query
    else:
        q = SupportTicket.query.filter_by(company_id=g.company_id)

    # Filtro por dono (agentes comuns só veem os próprios)
    if not is_sys_admin and g.user_role not in ('admin', 'supervisor'):
        q = q.filter_by(created_by=g.user_id)

    # Filtros opcionais
    status = request.args.get('status')
    if status and status in VALID_STATUSES:
        q = q.filter_by(status=status)

    priority = request.args.get('priority')
    if priority and priority in VALID_PRIORITIES:
        q = q.filter_by(priority=priority)

    category = request.args.get('category')
    if category and category in VALID_CATEGORIES:
        q = q.filter_by(category=category)

    assigned_to = request.args.get('assigned_to')
    if assigned_to and g.user_role in ('admin', 'supervisor'):
        try:
            q = q.filter_by(assigned_to=int(assigned_to))
        except ValueError:
            pass

    search = request.args.get('search', '').strip()
    if search:
        q = q.filter(SupportTicket.title.ilike(f'%{search}%'))

    # Data
    date_from = request.args.get('date_from')
    date_to   = request.args.get('date_to')
    if date_from:
        try:
            q = q.filter(SupportTicket.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(SupportTicket.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    # Ordenação
    sort_col = request.args.get('sort', 'created_at')
    order    = request.args.get('order', 'desc')
    sort_map = {
        'created_at': SupportTicket.created_at,
        'updated_at': SupportTicket.updated_at,
        'priority':   SupportTicket.priority,
        'status':     SupportTicket.status,
    }
    col = sort_map.get(sort_col, SupportTicket.created_at)
    q = q.order_by(col.desc() if order == 'desc' else col.asc())

    # Paginação
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))
    except ValueError:
        page, per_page = 1, 20

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'tickets':   [t.to_dict() for t in paginated.items],
        'total':     paginated.total,
        'page':      page,
        'per_page':  per_page,
        'pages':     paginated.pages,
    }), 200


@support_bp.route('/tickets', methods=['POST'])
@require_auth
def create_ticket():
    """
    Cria novo ticket.
    Body JSON: { title, description, category, priority? }
    """
    data = request.get_json(silent=True) or {}

    title       = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    category    = (data.get('category') or 'geral').strip().lower()
    priority    = (data.get('priority') or 'medium').strip().lower()

    errors = []
    if not title:
        errors.append('Título é obrigatório.')
    if len(title) > 255:
        errors.append('Título deve ter no máximo 255 caracteres.')
    if not description:
        errors.append('Descrição é obrigatória.')
    if category not in VALID_CATEGORIES:
        errors.append(f'Categoria inválida. Use: {", ".join(VALID_CATEGORIES)}')
    if priority not in VALID_PRIORITIES:
        errors.append(f'Prioridade inválida. Use: {", ".join(VALID_PRIORITIES)}')
    if errors:
        return jsonify({'error': ' '.join(errors)}), 400

    ticket = SupportTicket(
        company_id=g.company_id,
        created_by=g.user_id,
        title=title,
        description=description,
        category=category,
        priority=priority,
        status='open',
    )
    db.session.add(ticket)
    db.session.flush()  # gera ticket.id

    # Primeira mensagem automática = a própria descrição
    first_msg = TicketMessage(
        ticket_id=ticket.id,
        author_id=g.user_id,
        author_type='client',
        body=description,
    )
    db.session.add(first_msg)
    db.session.commit()

    logger.info('[SUPPORT] Ticket #%d criado por user %d', ticket.id, g.user_id)
    return jsonify(ticket.to_dict()), 201


# ─────────────────────────────────────────────────────────────────────────────
# TICKET – detalhe, atualização e remoção
# ─────────────────────────────────────────────────────────────────────────────

@support_bp.route('/tickets/<int:ticket_id>', methods=['GET'])
@require_auth
def get_ticket(ticket_id):
    """Retorna ticket com todas as mensagens."""
    ticket = _ticket_or_404(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket não encontrado'}), 404

    is_admin = (g.company_id == 1 and g.user_role in ('admin', 'supervisor'))

    # Agentes de outras empresas só veem seus próprios tickets (ou da empresa toda se for admin da empresa)
    if not is_admin:
        if g.user_role in ('admin', 'supervisor'):
            # Pode ver todos da sua empresa, o que o _ticket_or_404 já garante
            pass
        elif ticket.created_by != g.user_id:
            return jsonify({'error': 'Acesso negado'}), 403

    # Filtra notas internas para não-admin
    messages = ticket.messages.all()
    if not is_admin:
        messages = [m for m in messages if not m.is_internal]

    result = ticket.to_dict()
    result['messages'] = [m.to_dict() for m in messages]
    return jsonify(result), 200


@support_bp.route('/tickets/<int:ticket_id>', methods=['PATCH'])
@require_auth
def update_ticket(ticket_id):
    """
    Atualiza campos do ticket.
    Campos permitidos: status, priority, assigned_to, title (admin), category (admin)

    Regras:
    - Qualquer usuário pode enviar apenas { status: 'resolved' } no próprio ticket.
    - Admin pode alterar qualquer campo.
    """
    ticket = _ticket_or_404(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket não encontrado'}), 404

    is_admin = (g.company_id == 1 and g.user_role in ('admin', 'supervisor'))
    is_owner = ticket.created_by == g.user_id
    is_tenant_admin = (g.company_id == ticket.company_id and g.user_role in ('admin', 'supervisor'))

    if not is_admin and not is_owner and not is_tenant_admin:
        return jsonify({'error': 'Acesso negado'}), 403

    data = request.get_json(silent=True) or {}
    changed = False

    # Status
    new_status = data.get('status')
    if new_status is not None:
        if new_status not in VALID_STATUSES:
            return jsonify({'error': f'Status inválido: {new_status}'}), 400
        # Não-admin só pode fechar (resolved) o próprio ticket
        if not is_admin and new_status not in ('resolved',):
            return jsonify({'error': 'Você só pode marcar o ticket como resolvido.'}), 403
        if ticket.status != new_status:
            ticket.status = new_status
            if new_status in ('resolved', 'closed'):
                ticket.resolved_at = datetime.utcnow()
            changed = True

    # Prioridade (admin only)
    new_priority = data.get('priority')
    if new_priority is not None and is_admin:
        if new_priority not in VALID_PRIORITIES:
            return jsonify({'error': f'Prioridade inválida: {new_priority}'}), 400
        if ticket.priority != new_priority:
            ticket.priority = new_priority
            changed = True

    # Responsável (admin only)
    assigned_to = data.get('assigned_to')
    if assigned_to is not None and is_admin:
        if assigned_to == '' or assigned_to is None:
            ticket.assigned_to = None
            changed = True
        else:
            try:
                agent = User.query.filter_by(
                    id=int(assigned_to),
                    company_id=g.company_id,
                ).first()
                if not agent:
                    return jsonify({'error': 'Usuário não encontrado'}), 404
                ticket.assigned_to = agent.id
                # Ao atribuir, move para "em andamento" se ainda aberto
                if ticket.status == 'open':
                    ticket.status = 'in_progress'
                changed = True
            except (ValueError, TypeError):
                return jsonify({'error': 'assigned_to inválido'}), 400

    # Título e categoria (admin only)
    if is_admin:
        if data.get('title'):
            ticket.title = data['title'].strip()[:255]
            changed = True
        if data.get('category') and data['category'] in VALID_CATEGORIES:
            ticket.category = data['category']
            changed = True

    if changed:
        db.session.commit()
        logger.info('[SUPPORT] Ticket #%d atualizado por user %d', ticket.id, g.user_id)

    return jsonify(ticket.to_dict()), 200


@support_bp.route('/tickets/<int:ticket_id>', methods=['DELETE'])
@require_auth
def delete_ticket(ticket_id):
    """Remove ticket permanentemente (system_admin only)."""
    is_sys_admin = (g.company_id == 1 and g.user_role in ('admin', 'supervisor'))
    if not is_sys_admin:
        return jsonify({'error': 'Acesso restrito a administradores do sistema.'}), 403
        
    ticket = _ticket_or_404(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket não encontrado'}), 404

    db.session.delete(ticket)
    db.session.commit()
    logger.info('[SUPPORT] Ticket #%d removido por admin %d', ticket_id, g.user_id)
    return jsonify({'message': f'Ticket #{ticket_id} removido com sucesso.'}), 200


# ─────────────────────────────────────────────────────────────────────────────
# MENSAGENS
# ─────────────────────────────────────────────────────────────────────────────

@support_bp.route('/tickets/<int:ticket_id>/messages', methods=['GET'])
@require_auth
def list_messages(ticket_id):
    """Lista mensagens do ticket (filtra notas internas para não-admin)."""
    ticket = _ticket_or_404(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket não encontrado'}), 404

    is_admin = (g.company_id == 1 and g.user_role in ('admin', 'supervisor'))
    is_owner = ticket.created_by == g.user_id
    is_tenant_admin = (g.company_id == ticket.company_id and g.user_role in ('admin', 'supervisor'))
    
    if not is_admin and not is_owner and not is_tenant_admin:
        return jsonify({'error': 'Acesso negado'}), 403

    messages = ticket.messages.all()
    if not is_admin:
        messages = [m for m in messages if not m.is_internal]

    return jsonify([m.to_dict() for m in messages]), 200


@support_bp.route('/tickets/<int:ticket_id>/messages', methods=['POST'])
@require_auth
def send_message(ticket_id):
    """
    Envia mensagem no ticket.
    Body: { body, is_internal? }
    - is_internal só é aceito de admins/supervisores.
    - Reabrir ticket fechado ao responder (se não-admin).
    """
    ticket = _ticket_or_404(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket não encontrado'}), 404

    is_admin = (g.company_id == 1 and g.user_role in ('admin', 'supervisor'))
    is_owner = ticket.created_by == g.user_id
    is_tenant_admin = (g.company_id == ticket.company_id and g.user_role in ('admin', 'supervisor'))

    if not is_admin and not is_owner and not is_tenant_admin:
        return jsonify({'error': 'Acesso negado'}), 403

    data = request.get_json(silent=True) or {}
    body = (data.get('body') or '').strip()
    if not body:
        return jsonify({'error': 'Mensagem não pode ser vazia.'}), 400

    is_internal = bool(data.get('is_internal', False)) and is_admin
    author_type = 'support' if is_admin else 'client'

    msg = TicketMessage(
        ticket_id=ticket_id,
        author_id=g.user_id,
        author_type=author_type,
        body=body,
        is_internal=is_internal,
    )
    db.session.add(msg)

    # Reabrir ticket se estava resolvido e o cliente responde
    if not is_admin and ticket.status in ('resolved', 'closed'):
        ticket.status = 'open'
        ticket.resolved_at = None

    # Mover para em_andamento ao responder (admin)
    if is_admin and ticket.status == 'open':
        ticket.status = 'in_progress'

    db.session.commit()
    return jsonify(msg.to_dict()), 201


# ─────────────────────────────────────────────────────────────────────────────
# ESTATÍSTICAS (admin)
# ─────────────────────────────────────────────────────────────────────────────

@support_bp.route('/stats', methods=['GET'])
@require_auth
@require_role('admin', 'supervisor')
def get_stats():
    """
    Retorna métricas agregadas para o painel admin:
    - total por status
    - total por prioridade
    - total por categoria
    - tickets abertos sem responsável
    - tickets criados nos últimos 30 dias
    """
    from sqlalchemy import func
    
    is_sys_admin = (g.company_id == 1 and g.user_role in ('admin', 'supervisor'))
    
    if is_sys_admin:
        base = SupportTicket.query
    else:
        base = SupportTicket.query.filter_by(company_id=g.company_id)

    by_status = (
        db.session.query(SupportTicket.status, func.count(SupportTicket.id))
    )
    if not is_sys_admin:
        by_status = by_status.filter_by(company_id=g.company_id)
    by_status = by_status.group_by(SupportTicket.status).all()
    
    by_priority = (
        db.session.query(SupportTicket.priority, func.count(SupportTicket.id))
    )
    if not is_sys_admin:
        by_priority = by_priority.filter_by(company_id=g.company_id)
    by_priority = by_priority.group_by(SupportTicket.priority).all()
        
    by_category = (
        db.session.query(SupportTicket.category, func.count(SupportTicket.id))
    )
    if not is_sys_admin:
        by_category = by_category.filter_by(company_id=g.company_id)
    by_category = by_category.group_by(SupportTicket.category).all()

    unassigned_open = base.filter(
        SupportTicket.status.in_(['open', 'in_progress']),
        SupportTicket.assigned_to.is_(None),
    ).count()

    total = base.count()

    return jsonify({
        'total': total,
        'by_status':   {k: v for k, v in by_status},
        'by_priority': {k: v for k, v in by_priority},
        'by_category': {k: v for k, v in by_category},
        'unassigned_open': unassigned_open,
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# AGENTES disponíveis para atribuição
# ─────────────────────────────────────────────────────────────────────────────

@support_bp.route('/agents', methods=['GET'])
@require_auth
@require_role('admin', 'supervisor')
def list_agents():
    """Lista usuários ativos da empresa disponíveis para receber tickets."""
    agents = User.query.filter_by(
        company_id=g.company_id,
        status='active',
    ).all()
    return jsonify([
        {'id': u.id, 'name': u.name, 'role': u.role}
        for u in agents
    ]), 200
