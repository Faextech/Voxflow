"""
CRM Pipelines API
=================
Blueprint : crm_pipelines_bp
Prefix    : /api/crm

Endpoints
---------
GET    /api/crm/pipelines
POST   /api/crm/pipelines
PUT    /api/crm/pipelines/<id>
DELETE /api/crm/pipelines/<id>
POST   /api/crm/pipelines/<id>/archive
POST   /api/crm/pipelines/<id>/stages
PUT    /api/crm/stages/<id>
DELETE /api/crm/stages/<id>
PUT    /api/crm/pipelines/<pipeline_id>/stages/reorder
GET    /api/crm/pipeline/<pipeline_id>/deals
POST   /api/crm/deals
PUT    /api/crm/deals/<id>
PUT    /api/crm/deals/<id>/stage
PUT    /api/crm/deals/<id>/transfer
GET    /api/crm/pipelines/<id>/rules
POST   /api/crm/pipelines/<id>/rules
PUT    /api/crm/rules/<id>
DELETE /api/crm/rules/<id>
POST   /api/crm/rules/<id>/toggle
"""
import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models.deal import Deal
from app.models.pipeline import Pipeline, PipelineStage
from app.models.pipeline_transition_rule import PipelineTransitionRule
from app.models.deal_activity import DealActivity

logger = logging.getLogger(__name__)

crm_pipelines_bp = Blueprint('crm_pipelines', __name__, url_prefix='/api/crm')


# ---------------------------------------------------------------------------
# Auth decorator import — adjust path if your project differs
# ---------------------------------------------------------------------------
from app.auth import require_auth


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def serialize_pipeline(p, include_stages=False):
    d = {
        'id':          p.id,
        'name':        p.name,
        'color':       p.color,
        'icon':        p.icon,
        'position':    p.position,
        'is_default':  p.is_default,
        'is_archived': p.is_archived,
        'description': p.description,
        'deals_count': p.deals.count(),
        'deals_open':  p.deals.filter_by(status='open').count(),
        'stages_count': len(p.stages),
        'created_at':  p.created_at.isoformat() if p.created_at else None,
    }
    if include_stages:
        d['stages'] = [serialize_stage(s) for s in p.stages]
    return d


def serialize_stage(s):
    return {
        'id':                  s.id,
        'name':                s.name,
        'color':               s.color,
        'position':            s.position,
        'is_won':              s.is_won,
        'is_lost':             s.is_lost,
        'is_meeting':          s.is_meeting,
        'default_probability': s.default_probability,
        'pipeline_id':         s.pipeline_id,
        'automations_count':   len(s.automations),
    }


def serialize_deal(d):
    lead = d.lead
    return {
        'id':          d.id,
        'title':       d.title,
        'value':       float(d.value) if d.value else None,
        'currency':    d.currency,
        'probability': d.probability,
        'status':      d.status,
        'pipeline_id': d.pipeline_id,
        'stage_id':    d.stage_id,
        'lead_id':     d.lead_id,
        'agent_id':    d.agent_id,
        'lead': {
            'id':      lead.id,
            'name':    lead.name,
            'phone':   lead.numero_1,
            'company': lead.company_name,
            'email':   lead.email,
            'status':  lead.status,
            'notes':   lead.notes,
        } if lead else None,
        'stage_entered_at':    d.stage_entered_at.isoformat() if d.stage_entered_at else None,
        'last_activity_at':    d.last_activity_at.isoformat() if d.last_activity_at else None,
        'expected_close_date': d.expected_close_date.isoformat() if d.expected_close_date else None,
        'created_at':          d.created_at.isoformat() if d.created_at else None,
        'won_at':              d.won_at.isoformat() if d.won_at else None,
        'lost_at':             d.lost_at.isoformat() if d.lost_at else None,
        'has_recording':       any(a.type == 'call' and a.metadata_ and a.metadata_.get('recording_url') for a in d.activities)
    }


def serialize_rule(r):
    return {
        'id':                 r.id,
        'name':               r.name,
        'is_active':          r.is_active,
        'priority':           r.priority,
        'trigger':            r.trigger,
        'trigger_config':     r.trigger_config,
        'source_pipeline_id': r.source_pipeline_id,
        'target_pipeline_id': r.target_pipeline_id,
        'target_stage_id':    r.target_stage_id,
        'created_at':         r.created_at.isoformat() if r.created_at else None,
    }


def serialize_activity(a):
    return {
        'id':         a.id,
        'deal_id':    a.deal_id,
        'agent_id':   a.agent_id,
        'agent_name': a.agent.name if a.agent else 'Sistema',
        'type':       a.type,
        'title':      a.title,
        'body':       a.body,
        'metadata':   a.metadata_,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------

@crm_pipelines_bp.route('/pipelines', methods=['GET'])
@require_auth
def list_pipelines():
    """GET /api/crm/pipelines — list all pipelines for the tenant."""
    pipelines = (
        Pipeline.query
        .filter_by(company_id=g.company_id)
        .order_by(Pipeline.position.asc())
        .all()
    )
    return jsonify([serialize_pipeline(p, include_stages=True) for p in pipelines])


@crm_pipelines_bp.route('/pipelines', methods=['POST'])
@require_auth
def create_pipeline():
    """POST /api/crm/pipelines — create a pipeline."""
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    # Determine next position
    last = (
        Pipeline.query
        .filter_by(company_id=g.company_id)
        .order_by(Pipeline.position.desc())
        .first()
    )
    position = (last.position + 1) if last else 0

    pipeline = Pipeline(
        company_id=g.company_id,
        name=name,
        color=data.get('color', '#6366f1'),
        icon=data.get('icon'),
        description=data.get('description'),
        position=position,
        is_default=bool(data.get('is_default', False)),
    )
    db.session.add(pipeline)
    db.session.commit()

    logger.info('create_pipeline: pipeline_id=%s company_id=%s', pipeline.id, g.company_id)
    return jsonify(serialize_pipeline(pipeline, include_stages=True)), 201


@crm_pipelines_bp.route('/pipelines/<int:pipeline_id>', methods=['PUT'])
@require_auth
def update_pipeline(pipeline_id):
    """PUT /api/crm/pipelines/<id> — update pipeline metadata."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    data = request.get_json(silent=True) or {}

    allowed = ('name', 'color', 'icon', 'description', 'position', 'is_default', 'is_archived')
    for field in allowed:
        if field in data:
            setattr(pipeline, field, data[field])

    pipeline.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(serialize_pipeline(pipeline, include_stages=True))


@crm_pipelines_bp.route('/pipelines/<int:pipeline_id>', methods=['DELETE'])
@require_auth
def delete_pipeline(pipeline_id):
    """DELETE /api/crm/pipelines/<id> — delete if no open deals."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    open_count = pipeline.deals.filter_by(status='open').count()
    if open_count > 0:
        return jsonify({
            'error': f'Cannot delete pipeline with {open_count} open deal(s). '
                     'Close or transfer them first.',
        }), 409

    db.session.delete(pipeline)
    db.session.commit()

    logger.info('delete_pipeline: pipeline_id=%s company_id=%s', pipeline_id, g.company_id)
    return jsonify({'message': 'Pipeline deleted'}), 200


@crm_pipelines_bp.route('/pipelines/<int:pipeline_id>/archive', methods=['POST'])
@require_auth
def archive_pipeline(pipeline_id):
    """POST /api/crm/pipelines/<id>/archive — soft-archive a pipeline."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    pipeline.is_archived = True
    pipeline.updated_at  = datetime.utcnow()
    db.session.commit()

    logger.info('archive_pipeline: pipeline_id=%s company_id=%s', pipeline_id, g.company_id)
    return jsonify({'message': 'Pipeline archived', 'id': pipeline_id})


# ---------------------------------------------------------------------------
# Stage CRUD
# ---------------------------------------------------------------------------

@crm_pipelines_bp.route('/pipelines/<int:pipeline_id>/stages', methods=['POST'])
@require_auth
def create_stage(pipeline_id):
    """POST /api/crm/pipelines/<id>/stages — add a stage to a pipeline."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    # Auto-position at end
    last_position = max((s.position for s in pipeline.stages), default=-1)
    position = data.get('position', last_position + 1)

    stage = PipelineStage(
        pipeline_id=pipeline_id,
        company_id=g.company_id,
        name=name,
        color=data.get('color', '#6366f1'),
        position=int(position),
        default_probability=int(data.get('default_probability', 0)),
        is_won=bool(data.get('is_won', False)),
        is_lost=bool(data.get('is_lost', False)),
        is_meeting=bool(data.get('is_meeting', False)),
    )
    db.session.add(stage)
    db.session.commit()

    logger.info('create_stage: stage_id=%s pipeline_id=%s', stage.id, pipeline_id)
    return jsonify(serialize_stage(stage)), 201


@crm_pipelines_bp.route('/stages/<int:stage_id>', methods=['PUT'])
@require_auth
def update_stage(stage_id):
    """PUT /api/crm/stages/<id> — update a stage."""
    stage = PipelineStage.query.filter_by(id=stage_id, company_id=g.company_id).first()
    if stage is None:
        return jsonify({'error': 'Stage not found'}), 404

    data = request.get_json(silent=True) or {}
    allowed = ('name', 'color', 'position', 'default_probability', 'is_won', 'is_lost', 'is_meeting')
    for field in allowed:
        if field in data:
            setattr(stage, field, data[field])

    db.session.commit()
    return jsonify(serialize_stage(stage))


@crm_pipelines_bp.route('/stages/<int:stage_id>', methods=['DELETE'])
@require_auth
def delete_stage(stage_id):
    """DELETE /api/crm/stages/<id> — delete if no deals."""
    stage = PipelineStage.query.filter_by(id=stage_id, company_id=g.company_id).first()
    if stage is None:
        return jsonify({'error': 'Stage not found'}), 404

    deal_count = stage.deals.count()
    if deal_count > 0:
        return jsonify({
            'error': f'Cannot delete stage with {deal_count} deal(s). Move them first.',
        }), 409

    db.session.delete(stage)
    db.session.commit()

    logger.info('delete_stage: stage_id=%s company_id=%s', stage_id, g.company_id)
    return jsonify({'message': 'Stage deleted'}), 200


@crm_pipelines_bp.route('/pipelines/<int:pipeline_id>/stages/reorder', methods=['PUT'])
@require_auth
def reorder_stages(pipeline_id):
    """PUT /api/crm/pipelines/<id>/stages/reorder — reorder stages. Body: {stage_ids: [...]}"""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    data = request.get_json(silent=True) or {}
    stage_ids = data.get('stage_ids')
    if not isinstance(stage_ids, list) or not stage_ids:
        return jsonify({'error': 'stage_ids must be a non-empty list'}), 400

    # Build a lookup of stages belonging to this pipeline
    stages_by_id = {s.id: s for s in pipeline.stages}

    for position, sid in enumerate(stage_ids):
        stage = stages_by_id.get(int(sid))
        if stage is None:
            return jsonify({'error': f'Stage {sid} not found in pipeline {pipeline_id}'}), 404
        stage.position = position

    db.session.commit()
    return jsonify({'message': 'Stages reordered', 'stage_ids': stage_ids})


# ---------------------------------------------------------------------------
# Deal board
# ---------------------------------------------------------------------------

@crm_pipelines_bp.route('/pipeline/<int:pipeline_id>/deals', methods=['GET'])
@require_auth
def get_board(pipeline_id):
    """GET /api/crm/pipeline/<id>/deals — full Kanban board grouped by stage."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    board = []
    for stage in pipeline.stages:
        deals = (
            Deal.query
            .filter_by(stage_id=stage.id, company_id=g.company_id, status='open')
            .all()
        )
        board.append({**serialize_stage(stage), 'deals': [serialize_deal(d) for d in deals]})

    return jsonify({
        'pipeline': serialize_pipeline(pipeline),
        'board':    board,
    })


# ---------------------------------------------------------------------------
# Deal CRUD
# ---------------------------------------------------------------------------

@crm_pipelines_bp.route('/deals', methods=['POST'])
@require_auth
def create_deal():
    """POST /api/crm/deals — create a new deal."""
    data = request.get_json(silent=True) or {}

    required = ('pipeline_id', 'stage_id', 'lead_id', 'title')
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Validate pipeline & stage belong to this company
    pipeline = Pipeline.query.filter_by(
        id=data['pipeline_id'], company_id=g.company_id
    ).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    stage = PipelineStage.query.filter_by(
        id=data['stage_id'], pipeline_id=pipeline.id, company_id=g.company_id
    ).first()
    if stage is None:
        return jsonify({'error': 'Stage not found or does not belong to pipeline'}), 404

    deal = Deal(
        company_id=g.company_id,
        pipeline_id=pipeline.id,
        stage_id=stage.id,
        lead_id=int(data['lead_id']),
        agent_id=data.get('agent_id'),
        title=str(data['title']).strip(),
        value=data.get('value'),
        currency=data.get('currency', 'BRL'),
        probability=data.get('probability', stage.default_probability),
        status='open',
        stage_entered_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
    )
    db.session.add(deal)
    db.session.commit()

    logger.info('create_deal: deal_id=%s company_id=%s', deal.id, g.company_id)
    return jsonify(serialize_deal(deal)), 201


@crm_pipelines_bp.route('/deals/<int:deal_id>', methods=['PUT'])
@require_auth
def update_deal(deal_id):
    """PUT /api/crm/deals/<id> — update deal fields."""
    deal = Deal.query.filter_by(id=deal_id, company_id=g.company_id).first()
    if deal is None:
        return jsonify({'error': 'Deal not found'}), 404

    data = request.get_json(silent=True) or {}
    allowed = ('title', 'value', 'stage_id', 'status', 'probability',
               'expected_close_date', 'lost_reason', 'currency', 'agent_id')

    for field in allowed:
        if field in data:
            setattr(deal, field, data[field])

    # Handle status side-effects
    now = datetime.utcnow()
    if 'status' in data:
        if data['status'] == 'won' and deal.won_at is None:
            deal.won_at = now
        elif data['status'] == 'lost' and deal.lost_at is None:
            deal.lost_at = now

    deal.updated_at = now
    db.session.commit()

    return jsonify(serialize_deal(deal))


@crm_pipelines_bp.route('/deals/<int:deal_id>/stage', methods=['PUT'])
@require_auth
def move_deal_stage(deal_id):
    """PUT /api/crm/deals/<id>/stage — move deal to a new stage."""
    deal = Deal.query.filter_by(id=deal_id, company_id=g.company_id).first()
    if deal is None:
        return jsonify({'error': 'Deal not found'}), 404

    data = request.get_json(silent=True) or {}
    new_stage_id = data.get('stage_id')
    if not new_stage_id:
        return jsonify({'error': 'stage_id is required'}), 400

    new_stage = PipelineStage.query.filter_by(
        id=int(new_stage_id), company_id=g.company_id
    ).first()
    if new_stage is None:
        return jsonify({'error': 'Stage not found'}), 404

    from app.services.crm_service import move_to_stage
    move_to_stage(deal, new_stage, triggered_by=data.get('triggered_by', 'agent'))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('move_deal_stage: commit failed deal_id=%s', deal_id)
        return jsonify({'error': 'Internal server error'}), 500

    return jsonify(serialize_deal(deal))


@crm_pipelines_bp.route('/deals/<int:deal_id>/transfer', methods=['PUT'])
@require_auth
def transfer_deal(deal_id):
    """PUT /api/crm/deals/<id>/transfer — transfer deal to another pipeline."""
    deal = Deal.query.filter_by(id=deal_id, company_id=g.company_id).first()
    if deal is None:
        return jsonify({'error': 'Deal not found'}), 404

    data = request.get_json(silent=True) or {}
    target_pipeline_id = data.get('pipeline_id')
    target_stage_id    = data.get('stage_id')

    if not target_pipeline_id or not target_stage_id:
        return jsonify({'error': 'pipeline_id and stage_id are required'}), 400

    target_pipeline = Pipeline.query.filter_by(
        id=int(target_pipeline_id), company_id=g.company_id
    ).first()
    if target_pipeline is None:
        return jsonify({'error': 'Target pipeline not found'}), 404

    target_stage = PipelineStage.query.filter_by(
        id=int(target_stage_id), pipeline_id=target_pipeline.id, company_id=g.company_id
    ).first()
    if target_stage is None:
        return jsonify({'error': 'Target stage not found or does not belong to target pipeline'}), 404

    from app.services.pipeline_transfer_service import PipelineTransferService
    try:
        new_deal = PipelineTransferService.transfer(
            deal=deal,
            target_pipeline=target_pipeline,
            target_stage=target_stage,
            agent_id=data.get('agent_id'),
            reason=data.get('reason'),
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 409
    except Exception:
        logger.exception('transfer_deal: unexpected error deal_id=%s', deal_id)
        return jsonify({'error': 'Internal server error'}), 500

    return jsonify(serialize_deal(new_deal)), 201


@crm_pipelines_bp.route('/deals/<int:deal_id>/activities', methods=['GET'])
@require_auth
def list_deal_activities(deal_id):
    """GET /api/crm/deals/<id>/activities — list activities for a deal."""
    deal = Deal.query.filter_by(id=deal_id, company_id=g.company_id).first()
    if deal is None:
        return jsonify({'error': 'Deal not found'}), 404

    activities = (
        DealActivity.query
        .filter_by(deal_id=deal_id)
        .order_by(DealActivity.created_at.desc())
        .all()
    )
    return jsonify([serialize_activity(a) for a in activities])


# ---------------------------------------------------------------------------
# Pipeline Transition Rules
# ---------------------------------------------------------------------------

@crm_pipelines_bp.route('/pipelines/<int:pipeline_id>/rules', methods=['GET'])
@require_auth
def list_rules(pipeline_id):
    """GET /api/crm/pipelines/<id>/rules — list transition rules for a pipeline."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    rules = (
        PipelineTransitionRule.query
        .filter_by(source_pipeline_id=pipeline_id, company_id=g.company_id)
        .order_by(PipelineTransitionRule.priority.desc())
        .all()
    )
    return jsonify([serialize_rule(r) for r in rules])


@crm_pipelines_bp.route('/pipelines/<int:pipeline_id>/rules', methods=['POST'])
@require_auth
def create_rule(pipeline_id):
    """POST /api/crm/pipelines/<id>/rules — create a transition rule."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
    if pipeline is None:
        return jsonify({'error': 'Pipeline not found'}), 404

    data = request.get_json(silent=True) or {}
    required = ('name', 'trigger', 'target_pipeline_id', 'target_stage_id')
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Validate target pipeline/stage
    target_pipeline = Pipeline.query.filter_by(
        id=data['target_pipeline_id'], company_id=g.company_id
    ).first()
    if target_pipeline is None:
        return jsonify({'error': 'Target pipeline not found'}), 404

    target_stage = PipelineStage.query.filter_by(
        id=data['target_stage_id'],
        pipeline_id=target_pipeline.id,
        company_id=g.company_id,
    ).first()
    if target_stage is None:
        return jsonify({'error': 'Target stage not found'}), 404

    rule = PipelineTransitionRule(
        company_id=g.company_id,
        source_pipeline_id=pipeline_id,
        target_pipeline_id=int(data['target_pipeline_id']),
        target_stage_id=int(data['target_stage_id']),
        name=str(data['name']).strip(),
        trigger=str(data['trigger']),
        trigger_config=data.get('trigger_config', {}),
        priority=int(data.get('priority', 0)),
        is_active=bool(data.get('is_active', True)),
    )
    db.session.add(rule)
    db.session.commit()

    logger.info('create_rule: rule_id=%s pipeline_id=%s', rule.id, pipeline_id)
    return jsonify(serialize_rule(rule)), 201


@crm_pipelines_bp.route('/rules/<int:rule_id>', methods=['PUT'])
@require_auth
def update_rule(rule_id):
    """PUT /api/crm/rules/<id> — update a transition rule."""
    rule = PipelineTransitionRule.query.filter_by(
        id=rule_id, company_id=g.company_id
    ).first()
    if rule is None:
        return jsonify({'error': 'Rule not found'}), 404

    data = request.get_json(silent=True) or {}
    allowed = ('name', 'trigger', 'trigger_config', 'priority', 'is_active',
               'target_pipeline_id', 'target_stage_id')
    for field in allowed:
        if field in data:
            setattr(rule, field, data[field])

    db.session.commit()
    return jsonify(serialize_rule(rule))


@crm_pipelines_bp.route('/rules/<int:rule_id>', methods=['DELETE'])
@require_auth
def delete_rule(rule_id):
    """DELETE /api/crm/rules/<id> — delete a transition rule."""
    rule = PipelineTransitionRule.query.filter_by(
        id=rule_id, company_id=g.company_id
    ).first()
    if rule is None:
        return jsonify({'error': 'Rule not found'}), 404

    db.session.delete(rule)
    db.session.commit()

    logger.info('delete_rule: rule_id=%s company_id=%s', rule_id, g.company_id)
    return jsonify({'message': 'Rule deleted'})


@crm_pipelines_bp.route('/rules/<int:rule_id>/toggle', methods=['POST'])
@require_auth
def toggle_rule(rule_id):
    """POST /api/crm/rules/<id>/toggle — toggle rule is_active."""
    rule = PipelineTransitionRule.query.filter_by(
        id=rule_id, company_id=g.company_id
    ).first()
    if rule is None:
        return jsonify({'error': 'Rule not found'}), 404

    rule.is_active = not rule.is_active
    db.session.commit()

    logger.info(
        'toggle_rule: rule_id=%s is_active=%s company_id=%s',
        rule_id, rule.is_active, g.company_id,
    )
    return jsonify({'id': rule.id, 'is_active': rule.is_active})
