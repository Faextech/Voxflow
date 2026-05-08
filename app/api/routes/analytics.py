import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, g, jsonify
from sqlalchemy import func, case

from app.extensions import db
from app.auth import require_auth
from app.models.company import Company
from app.models.deal import Deal
from app.models.pipeline import Pipeline, PipelineStage
from app.models.lead import Lead
from app.models.call import Call
from app.models.campaign import Campaign

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
    period = request.args.get('period', 'month')

    # ── Cache Redis (60s) para evitar COUNT(*) repetidos ──────────────────────
    from app.services import redis_service
    _cache_key = f"voxflow:cache:analytics:dashboard:{cid}:{period}"
    if period != 'custom':
        _cached = redis_service.get(_cache_key)
        if _cached:
            return jsonify(_cached)

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

    result = {
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
    }
    if period != 'custom':
        redis_service.set(_cache_key, result, ex=60)
    return jsonify(result)


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
# AMD Metrics — qualidade de detecção de secretária eletrônica
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route('/amd')
@require_auth
def amd_metrics():
    """
    Métricas AMD por período e campanha com cache Redis (30s).
    Retorna: taxa de detecção humana, caixa postal, unknown,
             falsos positivos recuperados, breakdown por campanha.
    """
    cid = g.company_id
    date_from, date_to = _date_range()
    campaign_id = request.args.get('campaign_id', type=int)
    period = request.args.get('period', 'month')

    # Cache 30s (AMD muda frequentemente em campanhas ativas)
    from app.services import redis_service
    _cache_key = f"voxflow:cache:analytics:amd:{cid}:{period}:{campaign_id or 'all'}"
    if period != 'custom':
        _cached = redis_service.get(_cache_key)
        if _cached:
            return jsonify(_cached)

    q = Call.query.filter(
        Call.company_id  == cid,
        Call.direction   == 'outbound',
        Call.created_at  >= date_from,
        Call.created_at  <= date_to,
        Call.amd_result.isnot(None),
    )
    if campaign_id:
        q = q.filter(Call.campaign_id == campaign_id)

    calls = q.all()
    total_with_amd = len(calls)

    if total_with_amd == 0:
        return jsonify({
            'total_with_amd':       0,
            'human':                {'count': 0, 'pct': 0},
            'machine':              {'count': 0, 'pct': 0},
            'unknown':              {'count': 0, 'pct': 0},
            'false_positives_recovered': {'count': 0, 'pct': 0},
            'period': {'from': date_from.isoformat(), 'to': date_to.isoformat()},
        })

    human_count    = sum(1 for c in calls if c.amd_result == 'human')
    machine_count  = sum(1 for c in calls if c.amd_result in ('machine_start', 'machine_end_beep', 'machine_end_silence', 'machine_end_other'))
    unknown_count  = sum(1 for c in calls if c.amd_result in ('unknown', 'timeout'))
    recovered      = sum(1 for c in calls if c.amd_recovered)

    def pct(n):
        return round(n / total_with_amd * 100, 1) if total_with_amd else 0

    # Distribuição por campanha
    from app.models.campaign import Campaign
    from sqlalchemy import func as sqlfunc
    campaign_breakdown = []
    if not campaign_id:
        rows = (
            db.session.query(
                Call.campaign_id,
                Campaign.name,
                sqlfunc.count(Call.id).label('total'),
                sqlfunc.sum(case((Call.amd_result == 'human', 1), else_=0)).label('human'),
                sqlfunc.sum(case((Call.amd_result.in_(['machine_start','machine_end_beep','machine_end_silence','machine_end_other']), 1), else_=0)).label('machine'),
                sqlfunc.sum(case((Call.amd_result.in_(['unknown','timeout']), 1), else_=0)).label('unknown'),
                sqlfunc.sum(case((Call.amd_recovered == True, 1), else_=0)).label('recovered'),
            )
            .join(Campaign, Campaign.id == Call.campaign_id)
            .filter(
                Call.company_id == cid,
                Call.direction  == 'outbound',
                Call.created_at >= date_from,
                Call.created_at <= date_to,
                Call.amd_result.isnot(None),
            )
            .group_by(Call.campaign_id, Campaign.name)
            .order_by(sqlfunc.count(Call.id).desc())
            .limit(10)
            .all()
        )
        for r in rows:
            t = r.total or 1
            campaign_breakdown.append({
                'campaign_id':   r.campaign_id,
                'campaign_name': r.name,
                'total':         r.total,
                'human_pct':     round((r.human or 0) / t * 100, 1),
                'machine_pct':   round((r.machine or 0) / t * 100, 1),
                'unknown_pct':   round((r.unknown or 0) / t * 100, 1),
                'recovered':     r.recovered or 0,
            })

    result = {
        'total_with_amd': total_with_amd,
        'human':   {'count': human_count,   'pct': pct(human_count)},
        'machine': {'count': machine_count, 'pct': pct(machine_count)},
        'unknown': {'count': unknown_count, 'pct': pct(unknown_count)},
        'false_positives_recovered': {'count': recovered, 'pct': pct(recovered)},
        'campaign_breakdown': campaign_breakdown,
        'period': {'from': date_from.isoformat(), 'to': date_to.isoformat()},
    }
    if period != 'custom':
        redis_service.set(_cache_key, result, ex=30)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# Calls today — endpoint simples com cache Redis (30s)
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route('/calls-today')
@require_auth
def calls_today():
    cid = g.company_id
    from app.services import redis_service
    cache_key = f"voxflow:cache:calls_today:{cid}"
    cached = redis_service.get(cache_key)
    if cached:
        return jsonify(cached)

    from datetime import datetime
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total = Call.query.filter(
        Call.company_id == cid,
        Call.created_at >= today,
    ).count()
    answered = Call.query.filter(
        Call.company_id == cid,
        Call.created_at >= today,
        Call.status.in_(['completed', 'answered', 'in_call']),
    ).count()
    result = {'total': total, 'answered': answered}
    redis_service.set(cache_key, result, ex=30)
    return jsonify(result)


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


# ─────────────────────────────────────────────────────────────────────────────
# Campaign health alerts (AUTO-03)
# GET /api/analytics/alerts
# Returns a list of actionable alerts for the company's active campaigns.
# Thresholds: voicemail >40%, answer_rate <20%, balance <10 (BRL/USD units)
# ─────────────────────────────────────────────────────────────────────────────

VOICEMAIL_THRESHOLD  = 40   # %
ANSWER_THRESHOLD     = 20   # %
BALANCE_THRESHOLD    = 10   # currency units
ALERT_SAMPLE_SIZE    = 100  # last N calls per campaign


@analytics_bp.route('/alerts', methods=['GET'])
@require_auth
def campaign_alerts():
    cid = g.company_id
    alerts = []

    # ── Balance alert ──────────────────────────────────────────────────────
    company = Company.query.get(cid)
    if company:
        balance = float(company.get_balance())
        if balance < BALANCE_THRESHOLD:
            alerts.append({
                "type":     "low_balance",
                "severity": "critical" if balance <= 0 else "warning",
                "title":    "Saldo baixo",
                "message":  f"Saldo atual: R$ {balance:.2f}. Recarregue para continuar discando.",
                "campaign_id":   None,
                "campaign_name": None,
                "value":    balance,
            })

    # ── Per-campaign call quality alerts ──────────────────────────────────
    active_campaigns = Campaign.query.filter(
        Campaign.company_id == cid,
        Campaign.status.in_(["active", "running", "paused"]),
    ).all()

    for camp in active_campaigns:
        # Last ALERT_SAMPLE_SIZE calls for this campaign
        row = db.session.query(
            func.count(Call.id).label("total"),
            func.sum(case(
                (Call.status.in_(["completed", "answered", "in_call"]), 1), else_=0
            )).label("answered"),
            func.sum(case(
                (Call.status.in_(["voicemail", "machine"]), 1), else_=0
            )).label("voicemail"),
        ).filter(
            Call.company_id  == cid,
            Call.campaign_id == camp.id,
        ).order_by(Call.created_at.desc()).limit(ALERT_SAMPLE_SIZE).first()

        total    = int(row.total    or 0)
        answered = int(row.answered or 0)
        voicemail = int(row.voicemail or 0)

        if total < 10:
            # Not enough data for meaningful alert
            continue

        vm_rate     = round(voicemail / total * 100, 1)
        answer_rate = round(answered  / total * 100, 1)

        if vm_rate > VOICEMAIL_THRESHOLD:
            alerts.append({
                "type":          "voicemail_high",
                "severity":      "warning",
                "title":         f"Alta taxa de caixa postal — {camp.name}",
                "message":       f"{vm_rate}% das últimas {total} ligações foram para caixa postal (limite: {VOICEMAIL_THRESHOLD}%).",
                "campaign_id":   camp.id,
                "campaign_name": camp.name,
                "value":         vm_rate,
            })

        if answer_rate < ANSWER_THRESHOLD:
            alerts.append({
                "type":          "answer_low",
                "severity":      "warning",
                "title":         f"Taxa de atendimento baixa — {camp.name}",
                "message":       f"Apenas {answer_rate}% das últimas {total} ligações foram atendidas (mínimo: {ANSWER_THRESHOLD}%).",
                "campaign_id":   camp.id,
                "campaign_name": camp.name,
                "value":         answer_rate,
            })

    # Sort: critical first, then by campaign name
    alerts.sort(key=lambda a: (0 if a["severity"] == "critical" else 1, a["title"]))

    return jsonify({"alerts": alerts, "count": len(alerts)})


# ── CSV Export ────────────────────────────────────────────────────────────────

import csv
import io
from flask import make_response


@analytics_bp.route("/export/leads", methods=["GET"])
@require_auth
def export_leads_csv():
    """Export leads as CSV. Optional: ?campaign_id=&status="""
    from app.models.campaign import Campaign as _Camp

    campaign_id = request.args.get("campaign_id", type=int)
    status      = request.args.get("status", "").strip() or None

    q = Lead.query.filter_by(company_id=g.company_id)
    if campaign_id:
        q = q.filter_by(campaign_id=campaign_id)
    if status:
        q = q.filter_by(status=status)
    leads = q.order_by(Lead.created_at.desc()).all()

    # Build campaign name map
    camp_names = {c.id: c.name for c in _Camp.query.filter_by(company_id=g.company_id).all()}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID", "Nome", "Telefone 1", "Telefone 2", "Email", "Empresa",
                "Status", "Campanha", "Tentativas", "Criado em", "Atualizado em"])
    for l in leads:
        w.writerow([
            l.id, l.name or "", l.numero_1 or "", getattr(l, "numero_2", "") or "",
            l.email or "", l.company_name or "",
            l.status or "", camp_names.get(l.campaign_id, ""),
            getattr(l, "call_attempts", 0) or 0,
            l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "",
            l.updated_at.strftime("%Y-%m-%d %H:%M") if l.updated_at else "",
        ])

    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=leads.csv"
    return resp


@analytics_bp.route("/export/calls", methods=["GET"])
@require_auth
def export_calls_csv():
    """Export calls as CSV. Optional: ?from=YYYY-MM-DD&to=YYYY-MM-DD"""
    from app.models.campaign import Campaign as _Camp
    from app.models.lead import Lead as _Lead

    date_from = request.args.get("from", "").strip()
    date_to   = request.args.get("to", "").strip()

    q = Call.query.filter_by(company_id=g.company_id)
    if date_from:
        try:
            q = q.filter(Call.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import timedelta as _td
            q = q.filter(Call.created_at < datetime.strptime(date_to, "%Y-%m-%d") + _td(days=1))
        except ValueError:
            pass

    calls = q.order_by(Call.created_at.desc()).limit(50000).all()

    camp_names = {c.id: c.name for c in Campaign.query.filter_by(company_id=g.company_id).all()}
    lead_names = {l.id: (l.name or l.numero_1 or "") for l in _Lead.query.filter_by(company_id=g.company_id).all()}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID", "Data", "Duração (s)", "Status", "Lead", "Telefone", "Campanha",
                "Agente", "AMD resultado", "Call SID"])
    for c in calls:
        w.writerow([
            c.id,
            c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
            getattr(c, "duration", "") or "",
            getattr(c, "status", "") or "",
            lead_names.get(getattr(c, "lead_id", None), ""),
            getattr(c, "phone_number", "") or "",
            camp_names.get(getattr(c, "campaign_id", None), ""),
            getattr(c, "agent_id", "") or "",
            getattr(c, "amd_result", "") or "",
            getattr(c, "call_sid", "") or "",
        ])

    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=chamadas.csv"
    return resp


@analytics_bp.route("/export/dnc", methods=["GET"])
@require_auth
def export_dnc_csv():
    """Export DNC list as CSV."""
    from app.models.dnc import DNCEntry

    entries = DNCEntry.query.filter_by(company_id=g.company_id).order_by(DNCEntry.created_at.desc()).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID", "Número", "Motivo", "Adicionado em"])
    for e in entries:
        w.writerow([
            e.id,
            e.phone_e164 or "",
            e.reason or "",
            e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
        ])

    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=dnc.csv"
    return resp
