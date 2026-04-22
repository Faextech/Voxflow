"""
CRM Notifications API
=====================
Blueprint : crm_notifications_bp
Prefix    : /api/crm

Endpoints
---------
GET  /api/crm/notifications        — list notifications for the logged-in agent
PUT  /api/crm/notifications/read   — mark notification(s) as read
"""
import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models.agent import Agent
from app.models.notification import Notification

logger = logging.getLogger(__name__)

crm_notifications_bp = Blueprint('crm_notifications', __name__, url_prefix='/api/crm')

# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------
from app.auth import require_auth


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

def serialize_notification(n):
    return {
        'id':         n.id,
        'company_id': n.company_id,
        'agent_id':   n.agent_id,
        'deal_id':    n.deal_id,
        'type':       n.type,
        'message':    n.message,
        'is_read':    n.is_read,
        'read_at':    n.read_at.isoformat() if n.read_at else None,
        'created_at': n.created_at.isoformat() if n.created_at else None,
    }


# ---------------------------------------------------------------------------
# Helper — resolve agent for the current authenticated user
# ---------------------------------------------------------------------------

def _get_current_agent():
    """Return the Agent record for g.user_id / g.company_id, or None."""
    user_id = getattr(g, 'user_id', None)
    if user_id is None:
        return None
    return Agent.query.filter_by(user_id=user_id, company_id=g.company_id).first()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@crm_notifications_bp.route('/notifications', methods=['GET'])
@require_auth
def list_notifications():
    """
    GET /api/crm/notifications

    Query parameters
    ----------------
    unread : bool str  ('true' / '1') — return only unread notifications
    limit  : int       (default 20, max 200)
    """
    agent = _get_current_agent()
    if agent is None:
        return jsonify({'error': 'Agent record not found for this user'}), 404

    unread_only = request.args.get('unread', '').lower() in ('true', '1')
    limit = request.args.get('limit', default=20, type=int)
    limit = min(limit, 200)  # hard cap

    query = Notification.query.filter_by(
        company_id=g.company_id,
        agent_id=agent.id,
    )

    if unread_only:
        query = query.filter_by(is_read=False)

    notifications = (
        query
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    unread_count = Notification.query.filter_by(
        company_id=g.company_id,
        agent_id=agent.id,
        is_read=False,
    ).count()

    return jsonify({
        'notifications': [serialize_notification(n) for n in notifications],
        'unread_count':  unread_count,
        'total':         len(notifications),
    })


@crm_notifications_bp.route('/notifications/read', methods=['PUT'])
@require_auth
def mark_notifications_read():
    """
    PUT /api/crm/notifications/read

    Body (JSON)
    -----------
    {notification_ids: [1, 2, 3]}  — mark specific notifications as read
    {all: true}                    — mark ALL unread notifications as read
    """
    agent = _get_current_agent()
    if agent is None:
        return jsonify({'error': 'Agent record not found for this user'}), 404

    data = request.get_json(silent=True) or {}
    now  = datetime.utcnow()

    mark_all = bool(data.get('all', False))

    if mark_all:
        updated = (
            Notification.query
            .filter_by(company_id=g.company_id, agent_id=agent.id, is_read=False)
            .all()
        )
        for n in updated:
            n.is_read = True
            n.read_at = now
        db.session.commit()

        logger.info(
            'mark_notifications_read: marked all %d notifications read for agent_id=%s',
            len(updated), agent.id,
        )
        return jsonify({'message': f'{len(updated)} notification(s) marked as read'})

    notification_ids = data.get('notification_ids')
    if not isinstance(notification_ids, list) or not notification_ids:
        return jsonify({'error': 'Provide either notification_ids list or {all: true}'}), 400

    # Coerce to ints and filter to prevent cross-agent access
    safe_ids = [int(i) for i in notification_ids]

    notifications = Notification.query.filter(
        Notification.id.in_(safe_ids),
        Notification.company_id == g.company_id,
        Notification.agent_id == agent.id,
    ).all()

    if not notifications:
        return jsonify({'error': 'No matching notifications found'}), 404

    for n in notifications:
        n.is_read = True
        n.read_at = now

    db.session.commit()

    logger.info(
        'mark_notifications_read: marked %d notifications read for agent_id=%s',
        len(notifications), agent.id,
    )
    return jsonify({
        'message':          f'{len(notifications)} notification(s) marked as read',
        'updated_ids':      [n.id for n in notifications],
    })


@crm_notifications_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@require_auth
def mark_one_read(notification_id):
    """POST /api/crm/notifications/<id>/read — mark a single notification as read."""
    agent = _get_current_agent()
    if agent is None:
        return jsonify({'error': 'Agent record not found for this user'}), 404

    n = Notification.query.filter_by(
        id=notification_id, company_id=g.company_id, agent_id=agent.id
    ).first()
    if n is None:
        return jsonify({'error': 'Notification not found'}), 404

    n.is_read = True
    n.read_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Marked as read', 'id': notification_id})


@crm_notifications_bp.route('/notifications/read-all', methods=['POST'])
@require_auth
def mark_all_read():
    """POST /api/crm/notifications/read-all — mark all notifications as read."""
    agent = _get_current_agent()
    if agent is None:
        return jsonify({'error': 'Agent record not found for this user'}), 404

    now = datetime.utcnow()
    unread = Notification.query.filter_by(
        company_id=g.company_id, agent_id=agent.id, is_read=False
    ).all()
    for n in unread:
        n.is_read = True
        n.read_at = now
    db.session.commit()
    return jsonify({'message': f'{len(unread)} notification(s) marked as read'})
