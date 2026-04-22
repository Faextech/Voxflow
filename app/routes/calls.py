from datetime import datetime

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from app.auth import require_auth
from app.extensions import db
from app.models import Lead, Call, Campaign, Company
from app.services.twilio_service import TwilioService

calls_bp = Blueprint("calls", __name__)


def serialize_call(call):
    return {
        "id":               call.id,
        "company_id":       call.company_id,
        "campaign_id":      call.campaign_id,
        "campaign_name":    call.campaign.name if getattr(call, "campaign", None) else None,
        "lead_id":          call.lead_id,
        "lead_name":        call.lead.name if getattr(call, "lead", None) else None,
        "agent_id":         call.agent_id,
        "phone_dialed":     call.phone_dialed,
        "call_sid":         call.call_sid,
        "direction":        call.direction,
        "status":           call.status,
        "answered_by":      call.answered_by,
        "duration_seconds": call.duration_seconds,
        "attempt":          call.attempt,
        "recording_url":    call.recording_url,
        "disposition":      call.disposition,
        "hangup_cause":     call.hangup_cause,
        "created_at":       call.created_at.isoformat() if call.created_at else None,
        "ringing_at":       call.ringing_at.isoformat() if call.ringing_at else None,
        "answered_at":      call.answered_at.isoformat() if call.answered_at else None,
        "ended_at":         call.ended_at.isoformat() if call.ended_at else None,
    }


@calls_bp.route("/call/<int:lead_id>", methods=["POST"])
@require_auth
def call_lead(lead_id):
    # Verifica que o lead pertence ao tenant
    lead = Lead.query.filter_by(id=lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    phone_to_call = lead.get_primary_phone()
    if not phone_to_call:
        return jsonify({"error": "Lead sem número principal para discagem"}), 400

    try:
        company = Company.query.get(g.company_id)
        service = TwilioService.from_company(company)
        status_callback_url = request.host_url.rstrip("/") + "/api/twilio/status"

        last_attempt = (
            db.session.query(func.max(Call.attempt))
            .filter(Call.lead_id == lead.id, Call.company_id == g.company_id)
            .scalar()
        ) or 0

        call_sid = service.make_call(
            to_number=phone_to_call,
            status_callback_url=status_callback_url,
        )

        call = Call(
            company_id   = g.company_id,
            campaign_id  = lead.campaign_id,
            lead_id      = lead.id,
            phone_dialed = phone_to_call,
            call_sid     = call_sid,
            status       = "queued",
            direction    = "outbound",
            attempt      = last_attempt + 1,
            created_at   = datetime.utcnow(),
        )

        db.session.add(call)
        lead.status = "dialing"
        db.session.commit()

        # FIX 5: Mover o deal do CRM para a etapa "Em Contato" ao iniciar a ligação
        # (best-effort: nunca trava a resposta por erro de pipeline)
        try:
            from app.models.deal import Deal
            from app.models.pipeline import PipelineStage
            from app.services.crm_service import move_to_stage

            # Encontra o deal aberto mais recente deste lead
            deal = (
                Deal.query
                .filter_by(lead_id=lead.id, company_id=g.company_id, status="open")
                .order_by(Deal.created_at.desc())
                .first()
            )
            if deal:
                # Prioridade: "Em Contato" → "Feita a Ligação" → primeiro estágio não-ganho
                target_stage = (
                    PipelineStage.query
                    .filter(
                        PipelineStage.pipeline_id == deal.pipeline_id,
                        PipelineStage.company_id  == g.company_id,
                        PipelineStage.name.ilike("%em contato%"),
                    )
                    .first()
                ) or (
                    PipelineStage.query
                    .filter(
                        PipelineStage.pipeline_id == deal.pipeline_id,
                        PipelineStage.company_id  == g.company_id,
                        PipelineStage.name.ilike("%ligação%"),
                    )
                    .first()
                )
                if target_stage and deal.stage_id != target_stage.id:
                    move_to_stage(deal, target_stage, triggered_by="agent_dial")
                    db.session.commit()
        except Exception:
            pass  # nunca travar call_lead por erro de CRM

        return jsonify({
            "message": "Ligação iniciada",
            "call":    serialize_call(call),
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@calls_bp.route("/calls", methods=["GET"])
@require_auth
def list_calls():
    campaign_id = request.args.get("campaign_id", type=int)
    lead_id     = request.args.get("lead_id", type=int)
    status      = request.args.get("status")

    # company_id vem do JWT — não aceita query param
    query = Call.query.filter(Call.company_id == g.company_id)

    if campaign_id:
        query = query.filter(Call.campaign_id == campaign_id)
    if lead_id:
        query = query.filter(Call.lead_id == lead_id)
    if status:
        query = query.filter(Call.status == status)

    calls = query.order_by(Call.created_at.desc()).all()
    return jsonify([serialize_call(c) for c in calls]), 200


@calls_bp.route("/calls/active", methods=["GET"])
@require_auth
def get_active_call():
    active_call = (
        Call.query
        .filter(
            Call.company_id == g.company_id,
            Call.status.in_(["queued", "initiated", "ringing", "in_progress", "answered"]),
        )
        .order_by(Call.created_at.desc(), Call.id.desc())
        .first()
    )

    if not active_call:
        return jsonify({"active": False}), 200

    lead     = active_call.lead
    campaign = active_call.campaign

    return jsonify({
        "active": True,
        "call": {
            "id":          active_call.id,
            "call_sid":    active_call.call_sid,
            "status":      active_call.status,
            "phone":       active_call.phone_dialed,
            "started_at":  active_call.created_at.isoformat() if active_call.created_at else None,
            "answered_at": active_call.answered_at.isoformat() if active_call.answered_at else None,
            "direction":   active_call.direction,
            "attempt":     active_call.attempt,
        },
        "lead": {
            "id":    lead.id if lead else None,
            "name":  lead.name if lead else None,
            "company": lead.company_name if lead else None,
            "job":   lead.job_title if lead else None,
            "notes": lead.notes if lead else None,
            "phone": lead.numero_1 if lead else None,
        },
        "campaign": {
            "id":   campaign.id if campaign else None,
            "name": campaign.name if campaign else None,
        },
    }), 200


@calls_bp.route("/call/<int:call_id>", methods=["GET"])
@require_auth
def get_call(call_id):
    call = Call.query.filter_by(id=call_id, company_id=g.company_id).first()
    if not call:
        return jsonify({"error": "Call não encontrada"}), 404

    return jsonify(serialize_call(call)), 200


@calls_bp.route("/call/<int:call_id>/disposition", methods=["PUT"])
@require_auth
def update_call_disposition(call_id):
    call = Call.query.filter_by(id=call_id, company_id=g.company_id).first()
    if not call:
        return jsonify({"error": "Call não encontrada"}), 404

    data = request.get_json() or {}

    if data.get("disposition") is not None:
        call.disposition = data.get("disposition")
    if data.get("hangup_cause") is not None:
        call.hangup_cause = data.get("hangup_cause")
    if data.get("status") is not None:
        call.status = str(data.get("status")).replace("-", "_")
    if data.get("duration_seconds") is not None:
        call.duration_seconds = int(data.get("duration_seconds") or 0)
    if data.get("ended_at"):
        try:
            call.ended_at = datetime.fromisoformat(data["ended_at"])
        except Exception:
            pass

    if not call.ended_at and call.status in ["completed", "busy", "failed", "no_answer", "canceled"]:
        call.ended_at = datetime.utcnow()

    if call.answered_at and call.ended_at:
        delta = int((call.ended_at - call.answered_at).total_seconds())
        if delta >= 0:
            call.duration_seconds = delta

    if call.lead:
        if call.status in ["completed", "answered", "in_progress"]:
            call.lead.status = "contacted"
        elif call.status in ["failed", "busy", "no_answer", "canceled"]:
            call.lead.status = "new"

    db.session.commit()

    return jsonify({
        "message": "Chamada atualizada com sucesso",
        "call":    serialize_call(call),
    }), 200


@calls_bp.route("/call/<int:call_id>/hangup", methods=["POST"])
@require_auth
def hangup_call(call_id):
    call = Call.query.filter_by(id=call_id, company_id=g.company_id).first()
    if not call:
        return jsonify({"error": "Call não encontrada"}), 404

    if not call.call_sid:
        return jsonify({"error": "Chamada sem call_sid para encerrar na Twilio"}), 400

    try:
        company = Company.query.get(g.company_id)
        service = TwilioService.from_company(company)
        service.end_call(call.call_sid)

        if not call.ended_at:
            call.ended_at = datetime.utcnow()

        if call.answered_at and not call.duration_seconds:
            delta = int((call.ended_at - call.answered_at).total_seconds())
            if delta >= 0:
                call.duration_seconds = delta

        call.status = "completed"
        if call.lead:
            call.lead.status = "contacted"

        db.session.commit()

        return jsonify({
            "message": "Chamada encerrada com sucesso",
            "call":    serialize_call(call),
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@calls_bp.route("/dashboard/metrics", methods=["GET"])
@require_auth
def dashboard_metrics():
    # g.company_id garantido pelo JWT — sem query param
    leads_query    = Lead.query.filter(Lead.company_id == g.company_id)
    campaigns_query = Campaign.query.filter(Campaign.company_id == g.company_id)
    calls_query    = Call.query.filter(Call.company_id == g.company_id)

    total_leads     = leads_query.count()
    total_campaigns = campaigns_query.count()
    total_calls     = calls_query.count()
    new_leads       = leads_query.filter(Lead.status == "new").count()

    answered_calls = calls_query.filter(
        Call.status.in_(["completed", "in_progress", "answered"])
    ).count()
    failed_calls = calls_query.filter(
        Call.status.in_(["failed", "busy", "no_answer", "canceled"])
    ).count()

    total_duration = (
        db.session.query(func.coalesce(func.sum(Call.duration_seconds), 0))
        .filter(Call.company_id == g.company_id)
        .scalar()
    ) or 0

    avg_duration = round(total_duration / total_calls, 2) if total_calls else 0

    return jsonify({
        "total_leads":              total_leads,
        "new_leads":                new_leads,
        "total_campaigns":          total_campaigns,
        "total_calls":              total_calls,
        "answered_calls":           answered_calls,
        "failed_calls":             failed_calls,
        "total_duration_seconds":   total_duration,
        "average_duration_seconds": avg_duration,
    }), 200


@calls_bp.route("/reports/summary", methods=["GET"])
@require_auth
def reports_summary():
    calls = (
        Call.query
        .filter(Call.company_id == g.company_id)
        .order_by(Call.created_at.desc())
        .all()
    )

    total_calls    = len(calls)
    answered_calls = sum(1 for c in calls if c.status in ["completed", "in_progress", "answered"])
    failed_calls   = sum(1 for c in calls if c.status in ["failed", "busy", "no_answer", "canceled"])
    total_duration = sum((c.duration_seconds or 0) for c in calls)
    avg_duration   = round(total_duration / total_calls, 2) if total_calls else 0

    return jsonify({
        "total_calls":              total_calls,
        "answered_calls":           answered_calls,
        "failed_calls":             failed_calls,
        "total_duration_seconds":   total_duration,
        "average_duration_seconds": avg_duration,
    }), 200
