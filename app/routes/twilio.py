# ATENÇÃO: Este blueprint (twilio_bp) é registrado ANTES de twilio_voice_bp e
# por isso vence o conflito de URL para POST /api/twilio/status.
# Contém: status callback com débito de crédito + avanço do discador.
# twilio_voice.py contém as demais rotas (/browser-outgoing, /voice, etc).
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.call import Call

twilio_bp = Blueprint("twilio", __name__, url_prefix="/api/twilio")
logger = logging.getLogger(__name__)


# Mapeamento de status Twilio → nome da etapa da pipeline
_CALL_STATUS_TO_STAGE = {
    "ringing":     "Em Contato",
    "in-progress": "Em Contato",
    "answered":    "Em Contato",
    "no-answer":   "Não Atendeu",
    "busy":        "Não Atendeu",   # busy = linha ocupada, NÃO caixa postal
    "failed":      "Inválido",
}


def _auto_move_deal_by_call_status(call, call_status):
    """
    Tenta mover o deal do lead para a etapa correspondente ao status da chamada.
    Silencioso — jamais lança exceção para não travar o webhook do Twilio.
    """
    stage_name = _CALL_STATUS_TO_STAGE.get(call_status)
    if not stage_name or not call.lead_id:
        return

    # GUARD: Se a chamada já foi atendida (answered_at), não permitimos regredir para "Não Atendeu" ou "Inválido"
    # Isso evita webhooks atrasados de "status: failed" ou "no-answer" (após AMD ou silêncio) 
    # de limparem um lead que já está em conversa ou popup.
    if getattr(call, "answered_at", None) and call_status in ("no-answer", "failed", "busy"):
        return

    try:
        from app.models.deal import Deal
        from app.models.pipeline import PipelineStage

        # Pega o deal aberto mais recente do lead
        deal = (
            Deal.query
            .filter_by(lead_id=call.lead_id, company_id=call.company_id, status="open")
            .order_by(Deal.created_at.desc())
            .first()
        )
        if not deal:
            return

        # Encontra a etapa pelo nome dentro da pipeline do deal
        target_stage = (
            PipelineStage.query
            .filter_by(pipeline_id=deal.pipeline_id, name=stage_name)
            .first()
        )
        if not target_stage:
            return

        # Não regride etapas já avançadas (evita sobreescrever classificação manual)
        if deal.stage_id == target_stage.id:
            return

        from app.services.crm_service import move_to_stage
        move_to_stage(deal, target_stage, triggered_by="system")
        db.session.commit()

        logger.info(
            "_auto_move_deal_by_call_status: deal_id=%s lead_id=%s status=%s → etapa=%s",
            deal.id, call.lead_id, call_status, stage_name,
        )
    except Exception:
        logger.exception(
            "_auto_move_deal_by_call_status: erro silenciado para lead_id=%s status=%s",
            call.lead_id, call_status,
        )


def _get_value(name, default=None):
    return (
        request.values.get(name)
        or request.form.get(name)
        or request.args.get(name)
        or default
    )


def _parse_datetime(value):
    if not value:
        return None

    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue

    return None


@twilio_bp.route("/status", methods=["POST"])
def status_callback():
    print("=== /api/twilio/status chamado ===")
    print("Request values:", dict(request.values))

    call_sid = _get_value("CallSid")
    call_status = (_get_value("CallStatus") or "").lower().strip()
    call_duration = _get_value("CallDuration")
    answered_by = _get_value("AnsweredBy")
    from_number = _get_value("From")
    to_number = _get_value("To")
    timestamp_raw = _get_value("Timestamp")

    if not call_sid:
        return jsonify({"error": "CallSid não informado"}), 400

    call = Call.query.filter_by(call_sid=call_sid).first()

    if not call:
        print(f"[status_callback] Call não encontrada ainda para sid={call_sid}. Ignorando criação incompleta.")
        return jsonify({
            "message": "call ainda não persistida",
            "call_sid": call_sid
        }), 200

    if to_number:
        call.phone_dialed = to_number

    if call_status:
        # Não sobrescreve classificações definitivas do AMD/conferência com 'completed' genérico.
        # Ex: AMD detectou voicemail → call.status="voicemail_uncertain"; Twilio manda "completed"
        # logo em seguida — sem este guard o status seria apagado.
        _AMD_FINAL = {"voicemail", "voicemail_uncertain", "answered",
                      "no_answer", "busy", "failed"}
        if not (call_status == "completed" and call.status in _AMD_FINAL):
            call.status = call_status

    if hasattr(call, "from_number") and from_number:
        call.from_number = from_number

    if hasattr(call, "to_number") and to_number:
        call.to_number = to_number

    if hasattr(call, "answered_by") and answered_by:
        call.answered_by = answered_by

    event_time = _parse_datetime(timestamp_raw) or datetime.utcnow()

    if call_status in ["in-progress", "answered", "in_progress"]:
        if not getattr(call, "answered_at", None):
            call.answered_at = event_time

    if call_status in ["completed", "busy", "failed", "no-answer", "canceled", "no_answer"]:
        if not getattr(call, "ended_at", None):
            call.ended_at = event_time

    if call_duration:
        try:
            call.duration_seconds = int(call_duration)
        except (TypeError, ValueError):
            pass

    if call_status == "completed" and not getattr(call, "ended_at", None):
        call.ended_at = datetime.utcnow()

    if call_status in ["ringing", "queued"] and not getattr(call, "created_at", None):
        call.created_at = datetime.utcnow()

    db.session.commit()

    # Atualiza status do lead se ainda em "dialing/ringing" e o AMD não classificou ainda.
    # Evita que leads fiquem presos em status "dialing" quando o Twilio envia no-answer/busy/failed
    # antes do ring-timer de 50s disparar.
    if call_status in ("no-answer", "busy", "failed", "canceled") and call.lead_id:
        try:
            from app.models.lead import Lead as _Lead
            _lead = _Lead.query.get(call.lead_id)
            if _lead and _lead.status in ("dialing", "ringing"):
                _lead_status_map = {
                    "no-answer": "no_answer",
                    "busy":      "busy",
                    "failed":    "failed",
                    "canceled":  "no_answer",
                }
                _lead.status = _lead_status_map[call_status]
                db.session.commit()
        except Exception as _le:
            logger.warning("[STATUS] Erro ao atualizar lead status: %s", _le)
            db.session.rollback()

    # Automação: move o deal da pipeline conforme o status da chamada
    _auto_move_deal_by_call_status(call, call_status)

    # ── AVANÇO AUTOMÁTICO DO DISCADOR ───────────────────────────────────────
    # Usa on_call_ended() em vez de resume_auto_dialer_for_campaign() para:
    #   • verificar se há mais números do mesmo lead antes de avançar
    #   • respeitar current_call_sid (evita duplo-avanço quando AMD já avançou)
    #   • respeitar _cancelled_sids (leads pulados manualmente)
    _TERMINAL = {"completed", "failed", "no-answer", "busy", "canceled", "no_answer"}
    if call_status in _TERMINAL and call and call.campaign_id and call.company_id:
        try:
            from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS, on_call_ended
            _sess = AUTO_DIALER_SESSIONS.get(int(call.campaign_id))
            if _sess and _sess.get("current_call_sid") == call_sid:
                _cancelled = _sess.get("_cancelled_sids")
                if isinstance(_cancelled, set) and call_sid in _cancelled:
                    _cancelled.discard(call_sid)
                    logger.info("[STATUS→DIALER] SID %s cancelado manualmente — sem avanço", call_sid)
                else:
                    # Determina disposição respeitando o que AMD/conferência já classificou
                    if call.status in ("voicemail", "voicemail_uncertain"):
                        _disp, _force = "voicemail", True
                    elif call.status in ("no_answer", "busy", "failed"):
                        _disp, _force = call.status, False
                    else:
                        _disp = {
                            "no-answer": "no_answer",
                            "no_answer": "no_answer",
                            "busy":      "busy",
                            "failed":    "failed",
                            "canceled":  "no_answer",
                            "completed": "no_answer",
                        }.get(call_status, "no_answer")
                        _force = False
                    logger.info(
                        "[STATUS→DIALER] %s → disposition=%s force=%s | campaign=%s lead=%s",
                        call_status, _disp, _force, call.campaign_id, call.lead_id,
                    )
                    on_call_ended(
                        int(call.campaign_id), int(call.company_id),
                        call_sid, _disp, delay=0, force_advance=_force,
                    )
        except Exception as _exc:
            logger.error("[STATUS→DIALER] Erro ao avançar discador: %s", _exc)

    # ── Débito automático de crédito ────────────────────────────────────────
    if call_status == "completed" and call_duration and call.company_id:
        try:
            duration_sec = int(call_duration)
            if duration_sec > 0:
                from app.models.company import Company
                company = Company.query.get(call.company_id)
                if company:
                    company.debit_call(duration_seconds=duration_sec, call_sid=call_sid)
                    db.session.commit()
                    if not company.has_credit():
                        from app.services.twilio_subaccount_service import suspend_subaccount
                        suspend_subaccount(company)
                        logger.warning("[BILLING] Empresa %s sem saldo — subconta suspensa", company.id)
        except Exception as _billing_err:
            logger.error("[BILLING] Erro ao debitar chamada %s: %s", call_sid, _billing_err)
    # ─────────────────────────────────────────────────────────────────────────

    return jsonify({
        "message": "status atualizado",
        "call_sid": call_sid,
        "status": call.status,
        "duration_seconds": getattr(call, "duration_seconds", None)
    }), 200


@twilio_bp.route("/ping", methods=["GET", "POST"])
def ping():
    print("=== /api/twilio/ping ===")
    print("method:", request.method)
    print("args:", dict(request.args))
    print("form:", dict(request.form))
    return jsonify({"ok": True, "message": "pong"}), 200