"""
CRM Automations API
===================
Blueprint : crm_automations_bp
Prefix    : /api/crm

Endpoints
---------
GET    /api/crm/stages/<id>/automations
POST   /api/crm/stages/<id>/automations
PUT    /api/crm/automations/<id>
DELETE /api/crm/automations/<id>
GET    /api/crm/automations/logs
"""
import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models.pipeline import PipelineStage
from app.models.stage_automation import AutomationLog, StageAutomation

logger = logging.getLogger(__name__)

crm_automations_bp = Blueprint('crm_automations', __name__, url_prefix='/api/crm')

# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------
from app.auth import require_auth


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def serialize_automation(a):
    return {
        'id':         a.id,
        'stage_id':   a.stage_id,
        'company_id': a.company_id,
        'is_active':  a.is_active,
        'position':   a.position,
        'type':       a.type,
        'config':     a.config,
        'created_at': a.created_at.isoformat() if a.created_at else None,
        'updated_at': a.updated_at.isoformat() if a.updated_at else None,
    }


def serialize_log(log):
    return {
        'id':            log.id,
        'company_id':    log.company_id,
        'automation_id': log.automation_id,
        'deal_id':       log.deal_id,
        'lead_id':       log.lead_id,
        'type':          log.type,
        'status':        log.status,
        'error_message': log.error_message,
        'executed_at':   log.executed_at.isoformat() if log.executed_at else None,
        'payload':       log.payload,
    }


# ---------------------------------------------------------------------------
# Stage Automations
# ---------------------------------------------------------------------------

@crm_automations_bp.route('/stages/<int:stage_id>/automations', methods=['GET'])
@require_auth
def list_automations(stage_id):
    """GET /api/crm/stages/<id>/automations — list automations for a stage."""
    stage = PipelineStage.query.filter_by(id=stage_id, company_id=g.company_id).first()
    if stage is None:
        return jsonify({'error': 'Stage not found'}), 404

    automations = (
        StageAutomation.query
        .filter_by(stage_id=stage_id, company_id=g.company_id)
        .order_by(StageAutomation.position.asc())
        .all()
    )
    return jsonify([serialize_automation(a) for a in automations])


@crm_automations_bp.route('/stages/<int:stage_id>/automations', methods=['POST'])
@require_auth
def create_automation(stage_id):
    """POST /api/crm/stages/<id>/automations — create an automation."""
    stage = PipelineStage.query.filter_by(id=stage_id, company_id=g.company_id).first()
    if stage is None:
        return jsonify({'error': 'Stage not found'}), 404

    data = request.get_json(silent=True) or {}

    automation_type = (data.get('type') or '').strip()
    if not automation_type:
        return jsonify({'error': 'type is required'}), 400

    allowed_types = {'send_whatsapp', 'notify_agent', 'create_task', 'update_deal'}
    if automation_type not in allowed_types:
        return jsonify({
            'error': f'type must be one of: {", ".join(sorted(allowed_types))}',
        }), 400

    # Auto-position at end
    last = (
        StageAutomation.query
        .filter_by(stage_id=stage_id, company_id=g.company_id)
        .order_by(StageAutomation.position.desc())
        .first()
    )
    position = (last.position + 1) if last else 0

    automation = StageAutomation(
        stage_id=stage_id,
        company_id=g.company_id,
        type=automation_type,
        config=data.get('config', {}),
        is_active=bool(data.get('is_active', True)),
        position=int(data.get('position', position)),
    )
    db.session.add(automation)
    db.session.commit()

    logger.info(
        'create_automation: automation_id=%s stage_id=%s type=%s',
        automation.id, stage_id, automation_type,
    )
    return jsonify(serialize_automation(automation)), 201


@crm_automations_bp.route('/automations/<int:automation_id>', methods=['PUT'])
@require_auth
def update_automation(automation_id):
    """PUT /api/crm/automations/<id> — update an automation."""
    automation = StageAutomation.query.filter_by(
        id=automation_id, company_id=g.company_id
    ).first()
    if automation is None:
        return jsonify({'error': 'Automation not found'}), 404

    data = request.get_json(silent=True) or {}
    allowed = ('type', 'config', 'is_active', 'position')
    for field in allowed:
        if field in data:
            setattr(automation, field, data[field])

    automation.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(serialize_automation(automation))


@crm_automations_bp.route('/automations/<int:automation_id>', methods=['DELETE'])
@require_auth
def delete_automation(automation_id):
    """DELETE /api/crm/automations/<id> — remove an automation."""
    automation = StageAutomation.query.filter_by(
        id=automation_id, company_id=g.company_id
    ).first()
    if automation is None:
        return jsonify({'error': 'Automation not found'}), 404

    db.session.delete(automation)
    db.session.commit()

    logger.info(
        'delete_automation: automation_id=%s company_id=%s', automation_id, g.company_id
    )
    return jsonify({'message': 'Automation deleted'})


# ---------------------------------------------------------------------------
# Automation Logs
# ---------------------------------------------------------------------------

@crm_automations_bp.route('/automations/logs', methods=['GET'])
@require_auth
def list_logs():
    """
    GET /api/crm/automations/logs

    Query parameters
    ----------------
    deal_id : int  (optional)
    status  : str  (optional) — success|failed|skipped
    limit   : int  (default 50)
    """
    deal_id = request.args.get('deal_id', type=int)
    status  = request.args.get('status')
    limit   = request.args.get('limit', default=50, type=int)
    limit   = min(limit, 500)  # hard cap

    query = AutomationLog.query.filter_by(company_id=g.company_id)

    if deal_id:
        query = query.filter_by(deal_id=deal_id)
    if status:
        query = query.filter_by(status=status)

    logs = query.order_by(AutomationLog.executed_at.desc()).limit(limit).all()
    return jsonify([serialize_log(log) for log in logs])
