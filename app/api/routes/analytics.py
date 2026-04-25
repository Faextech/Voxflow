import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, g, jsonify
from sqlalchemy import func, case

from app.extensions import db
from app.auth import require_auth
from app.models.deal import Deal
from app.models.pipeline import Pipeline, PipelineStage
from app.models.lead import Lead
from app.models.call import Call

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')


def _date_range():
    period = request.args.get('period', 'month')
    now = datetime.utcnow()

    if period == 'day':
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now

    if period == 'week':
        return now - timedelta(days=7), now

    if period == 'custom':
        try:
            date_from = datetime.fromisoformat(request.args.get('date_from', ''))
        except (ValueError, TypeError):
            date_from = now - timedelta(days=30)
        try:
            # include the full last day
            date_to = datetime.fromisoformat(request.args.get('date_to', ''))
            date_to = date_to.replace(hour=23, minute=59, second=59)
        except (ValueError, TypeError):
            date_to = now
        return date_from, date_to

    # default: month (30 days)
    return now - timedelta(days=30), now


# ─────────────────────────────────────────────────────────────────────────────
# KPI dashboard endpoint
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route('/dashboard')
@require_auth
def dashboard_metrics():
    cid = g.company_id
    date_from, date_to = _date_range()

    # ── Deal aggregation ─────────────────────────────────────────────
    deal_row = db.session.query(
        func.count(Deal.id).label('total'),
        func.sum(case((Deal.status == 'won',  1), else_=0)).label('won'),
        func.sum(case((Deal.status == 'lost', 1), else_=0)).label('lost'),
        func.sum(case((Deal.status == 'open', 1), else_=0)).label('open_count'),
        func.avg(case((Deal.status == 'won',  Deal.value), else_=None)).label('avg_ticket'),
        func.sum(case((Deal.status == 'won',  Deal.value), else_=0)).label('total_revenue'),
        func.sum(case((Deal.status == 'lost', Deal.value), else_=0)).label('total_lost_value'),
    ).filter(
        Deal.company_id == cid,
        Deal.created_at >= date_from,
        Deal.created_at <= date_to,
    ).first()

    won_count     = int(deal_row.won or 0)
    lost_count    = int(deal_row.lost or 0)
    open_count    = int(deal_row.open_count or 0)
    total_deals   = int(deal_row.total or 0)
    avg_ticket    = round(float(deal_row.avg_ticket or 0), 2)
    total_revenue = round(float(deal_row.total_revenue or 0), 2)
    total_lost_value = round(float(deal_row.total_lost_value or 0), 2)

    closed = won_count + lost_count
    conversion_rate = round(won_count / closed * 100, 1) if closed else 0

    # avg days to close — compute in Python (DB-agnostic)
    won_dates = db.session.query(Deal.created_at, Deal.won_at).filter(
        Deal.company_id == cid,
        Deal.status == 'won',
        Deal.created_at >= date_from,
        Deal.created_at <= date_to,
        Deal.won_at.isnot(None),
    ).all()
    days_list = [(d.won_at - d.created_at).days for d in won_dates if d.won_at]
    avg_days_to_close = round(sum(days_list) / len(days_list), 1) if days_list else 0

    # ── Lead totals ──────────────────────────────────────────────────
    total_leads = Lead.query.filter(
        Lead.company_id == cid,
        Lead.created_at >= date_from,
        Lead.created_at <= date_to,
    ).count()

    # ── Call aggregation ─────────────────────────────────────────────
    call_row = db.session.query(
        func.count(Call.id).label('total'),
        func.sum(case(
            (Call.status.in_(['completed', 'answered', 'in_call']), 1), else_=0
        )).label('answered'),
        func.sum(case((Call.status == 'no_answer', 1), else_=0)).label('no_answer'),
        func.sum(case((Call.status == 'busy',      1), else_=0)).label('busy'),
        func.sum(case(
            (Call.status.in_(['voicemail', 'machine']), 1), else_=0
        )).label('voicemail'),
        func.avg(Call.duration_seconds).label('avg_duration'),
    ).filter(
        Call.company_id == cid,
        Call.created_at >= date_from,
        Call.created_at <= date_to,
    ).first()

    total_calls  = int(call_row.total or 0)
    answered     = int(call_row.answered or 0)
    no_answer    = int(call_row.no_answer or 0)
    busy         = int(call_row.busy or 0)
    voicemail    = int(call_row.voicemail or 0)
    contact_rate = round(answered / total_calls * 100, 1) if total_calls else 0
    avg_duration = round(float(call_row.avg_duration or 0))

    return jsonify({
        'period': {'from': date_from.isoformat(), 'to': date_to.isoformat()},
        'deals': {
            'total':              total_deals,
            'won':                won_count,
            'lost':               lost_count,
            'open':               open_count,
            'conversion_rate':    conversion_rate,
            'avg_days_to_close':  avg_days_to_close,
            'avg_ticket':         avg_ticket,
            'total_revenue':      total_revenue,
            'total_lost_value':   total_lost_value,
        },
        'leads': {'total': total_leads},
        'calls': {
            'total':               total_calls,
            'answered':            answered,
            'no_answer':           no_answer,
            'busy':                busy,
            'voicemail':           voicemail,
            'contact_rate':        contact_rate,
            'avg_duration_seconds': avg_duration,
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# Funnel: deals per pipeline stage
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route('/funnel')
@require_auth
def funnel_data():
    cid = g.company_id
    date_from, date_to = _date_range()
    pipeline_id = request.args.get('pipeline_id', type=int)

    # Subquery: aggregate deals per stage within the time window
    deal_agg = db.session.query(
        Deal.stage_id.label('stage_id'),
        func.count(Deal.id).label('deal_count'),
        func.sum(Deal.value).label('total_value'),
    ).filter(
        Deal.company_id == cid,
        Deal.created_at >= date_from,
        Deal.created_at <= date_to,
    ).group_by(Deal.stage_id).subquery('deal_agg')

    # All stages (outer join → 0 for stages with no deals in period)
    q = db.session.query(
        PipelineStage.id,
        PipelineStage.name,
        PipelineStage.position,
        PipelineStage.color,
        PipelineStage.is_won,
        PipelineStage.is_lost,
        func.coalesce(deal_agg.c.deal_count, 0).label('deal_count'),
        func.coalesce(deal_agg.c.total_value, 0).label('total_value'),
    ).outerjoin(deal_agg, deal_agg.c.stage_id == PipelineStage.id)\
     .filter(PipelineStage.company_id == cid)

    if pipeline_id:
        q = q.filter(PipelineStage.pipeline_id == pipeline_id)

    stages = q.order_by(PipelineStage.position).all()

    max_count = max((s.deal_count for s in stages), default=1) or 1
    result = []
    for s in stages:
        result.append({
            'id':          s.id,
            'name':        s.name,
            'position':    s.position,
            'color':       s.color,
            'is_won':      s.is_won,
            'is_lost':     s.is_lost,
            'deal_count':  s.deal_count,
            'total_value': float(s.total_value or 0),
            'pct_of_top':  round(s.deal_count / max_count * 100, 1),
        })

    return jsonify({'stages': result})


# ─────────────────────────────────────────────────────────────────────────────
# Time-series: daily counts for leads, calls, and won deals
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route('/time-series')
@require_auth
def time_series():
    cid = g.company_id
    date_from, date_to = _date_range()

    leads_by_day = db.session.query(
        func.date(Lead.created_at).label('day'),
        func.count(Lead.id).label('count'),
    ).filter(
        Lead.company_id == cid,
        Lead.created_at >= date_from,
        Lead.created_at <= date_to,
    ).group_by(func.date(Lead.created_at))\
     .order_by(func.date(Lead.created_at)).all()

    calls_by_day = db.session.query(
        func.date(Call.created_at).label('day'),
        func.count(Call.id).label('count'),
    ).filter(
        Call.company_id == cid,
        Call.created_at >= date_from,
        Call.created_at <= date_to,
    ).group_by(func.date(Call.created_at))\
     .order_by(func.date(Call.created_at)).all()

    won_by_day = db.session.query(
        func.date(Deal.won_at).label('day'),
        func.count(Deal.id).label('count'),
    ).filter(
        Deal.company_id == cid,
        Deal.status == 'won',
        Deal.won_at.isnot(None),
        Deal.won_at >= date_from,
        Deal.won_at <= date_to,
    ).group_by(func.date(Deal.won_at))\
     .order_by(func.date(Deal.won_at)).all()

    return jsonify({
        'leads': [{'day': str(r.day), 'count': r.count} for r in leads_by_day],
        'calls': [{'day': str(r.day), 'count': r.count} for r in calls_by_day],
        'won':   [{'day': str(r.day), 'count': r.count} for r in won_by_day],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline list (for filter dropdown)
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route('/pipelines')
@require_auth
def list_pipelines():
    cid = g.company_id
    pipelines = Pipeline.query.filter_by(
        company_id=cid, is_archived=False
    ).order_by(Pipeline.position).all()
    return jsonify([{'id': p.id, 'name': p.name} for p in pipelines])
