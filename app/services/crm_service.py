"""
CRM Service — high-level helpers for deal lifecycle management.

All public functions assume they are called inside an active application/request
context so that db.session is available.
"""
import logging
from datetime import datetime

from app.extensions import db
from app.models.deal import Deal
from app.models.deal_activity import DealActivity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_deal_for_lead(lead, pipeline_id=None, agent_id=None, company_id=None):
    """
    Return the existing open deal for *lead* in the given pipeline, or create
    one if none exists.

    Parameters
    ----------
    lead        : Lead ORM instance
    pipeline_id : int | None — if None the first non-archived pipeline is used
    agent_id    : int | None — assigned agent for newly created deals
    company_id  : int | None — falls back to lead.company_id

    Returns
    -------
    (deal, created) : (Deal, bool)
    """
    cid = company_id or lead.company_id

    # Resolve pipeline
    if pipeline_id is None:
        from app.models.pipeline import Pipeline
        pipeline = (
            Pipeline.query
            .filter_by(company_id=cid, is_archived=False)
            .order_by(Pipeline.is_default.desc(), Pipeline.position.asc())
            .first()
        )
        if pipeline is None:
            logger.warning('ensure_deal_for_lead: no pipeline found for company_id=%s', cid)
            return None, False
        pipeline_id = pipeline.id
    else:
        from app.models.pipeline import Pipeline
        pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=cid).first()
        if pipeline is None:
            logger.warning(
                'ensure_deal_for_lead: pipeline %s not found for company_id=%s',
                pipeline_id, cid,
            )
            return None, False

    # Check for existing open deal
    existing = Deal.query.filter_by(
        company_id=cid,
        lead_id=lead.id,
        pipeline_id=pipeline_id,
        status='open',
    ).first()

    if existing:
        logger.debug('ensure_deal_for_lead: returning existing deal id=%s', existing.id)
        return existing, False

    # Resolve first stage
    first_stage = None
    if pipeline.stages:
        first_stage = pipeline.stages[0]

    if first_stage is None:
        logger.warning(
            'ensure_deal_for_lead: pipeline %s has no stages — cannot create deal',
            pipeline_id,
        )
        return None, False

    title = getattr(lead, 'name', None) or f'Lead #{lead.id}'

    deal = Deal(
        company_id=cid,
        pipeline_id=pipeline_id,
        stage_id=first_stage.id,
        lead_id=lead.id,
        agent_id=agent_id,
        title=title,
        probability=first_stage.default_probability,
        status='open',
        stage_entered_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
    )
    db.session.add(deal)
    db.session.flush()  # get deal.id without full commit

    logger.info(
        'ensure_deal_for_lead: created deal id=%s for lead id=%s pipeline=%s',
        deal.id, lead.id, pipeline_id,
    )
    return deal, True


def add_activity(deal, type, title=None, body=None, agent_id=None, metadata=None):
    """
    Append a DealActivity to *deal* and refresh deal.last_activity_at.

    Parameters
    ----------
    deal     : Deal ORM instance
    type     : str  — activity type (call|note|email|whatsapp|meeting|stage_change|…)
    title    : str | None
    body     : str | None
    agent_id : int | None
    metadata : dict | None  — stored as JSON

    Returns
    -------
    DealActivity
    """
    now = datetime.utcnow()

    activity = DealActivity(
        company_id=deal.company_id,
        deal_id=deal.id,
        agent_id=agent_id,
        type=type,
        title=title,
        body=body,
        metadata_=metadata,
        created_at=now,
    )
    db.session.add(activity)

    deal.last_activity_at = now
    db.session.add(deal)

    logger.debug(
        'add_activity: type=%s deal_id=%s agent_id=%s',
        type, deal.id, agent_id,
    )
    return activity


def move_to_stage(deal, new_stage, triggered_by='agent'):
    """
    Move *deal* to *new_stage*, record a stage_change activity, update
    stage_entered_at, and fire the AutomationEngine for the new stage.

    Parameters
    ----------
    deal         : Deal ORM instance
    new_stage    : PipelineStage ORM instance
    triggered_by : str — 'agent' | 'rule' | 'system'

    Returns
    -------
    Deal (updated, not yet committed)
    """
    old_stage_id = deal.stage_id
    old_stage_name = deal.stage.name if deal.stage else str(old_stage_id)
    now = datetime.utcnow()

    deal.stage_id = new_stage.id
    deal.stage_entered_at = now
    deal.last_activity_at = now

    # Update status based on stage flags
    if new_stage.is_won:
        deal.status = 'won'
        deal.won_at = now
    elif new_stage.is_lost:
        deal.status = 'lost'
        deal.lost_at = now
    # meeting stages keep status='open'

    db.session.add(deal)

    # Record stage-change activity
    add_activity(
        deal=deal,
        type='stage_change',
        title=f'Moved to {new_stage.name}',
        body=f'Stage changed from "{old_stage_name}" to "{new_stage.name}"',
        metadata={
            'old_stage_id': old_stage_id,
            'new_stage_id': new_stage.id,
            'triggered_by': triggered_by,
        },
    )

    logger.info(
        'move_to_stage: deal_id=%s %s -> %s (triggered_by=%s)',
        deal.id, old_stage_id, new_stage.id, triggered_by,
    )

    # Fire automations (import deferred to avoid circular imports at module load)
    try:
        from app.services.automation_engine import AutomationEngine
        engine = AutomationEngine(deal=deal, stage=new_stage)
        engine.run()
    except Exception:
        logger.exception(
            'move_to_stage: automation engine error for deal_id=%s stage_id=%s',
            deal.id, new_stage.id,
        )

    return deal
