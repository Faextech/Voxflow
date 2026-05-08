import os

from flask import Blueprint, jsonify, request, g
from app.models.agent import Agent
from app.models.user import User
from app.services.call_bridge import ACTIVE_CONFERENCES_BY_NAME
from app.extensions import db
from app.auth import require_auth, require_role

supervisor_bp = Blueprint("supervisor", __name__, url_prefix="/api/supervisor")

@supervisor_bp.route("/realtime", methods=["GET"])
@require_auth
def realtime_status():
    """
    Retorna o estado em tempo real de todos os operadores e conferências ativas.
    Apenas para administradores do mesmo tenant.
    """
    if g.user_role not in ('admin', 'supervisor'):
        return jsonify({"error": "Acesso negado. Apenas administradores podem acessar o supervisor."}), 403

    # Filtrar apenas agentes da mesma empresa
    agents = db.session.query(Agent).join(User).filter(User.company_id == g.company_id).all()
    
    # Mapear conferências por agente para facilitar o front-end
    active_conf_by_agent = {}
    for conf_name, data in ACTIVE_CONFERENCES_BY_NAME.items():
        aid = data.get("agent_id")
        if aid:
            active_conf_by_agent[aid] = {
                "conference_name": conf_name,
                "status": data.get("status"),
                "lead_name": data.get("lead_name"),
                "phone_number": data.get("phone_number"),
                "created_at": data.get("created_at"),
                "lead_answered_at": data.get("lead_answered_at")
            }

    agents_list = []
    for a in agents:
        agents_list.append({
            "id": a.id,
            "name": a.user.name, # Usa o nome do User vinculado
            "status": a.status or "offline",
            "last_active": a.last_seen_at.isoformat() if a.last_seen_at else None,
            "active_call": active_conf_by_agent.get(a.id)
        })

    return jsonify({
        "agents": agents_list,
        "total_active_conferences": len(ACTIVE_CONFERENCES_BY_NAME)
    }), 200


@supervisor_bp.route("/listen-live", methods=["POST"])
@require_auth
@require_role("admin", "supervisor")
def listen_live():
    """
    Supervisor entra silenciosamente em uma conferência ativa com muted=true.
    Body: { "conference_name": "auto_1_2_abc123" }

    Usa Twilio REST para ligar para client:<supervisor_identity> com TwiML
    que entra na conference como ouvinte (muted, sem beep, sem encerrar ao sair).
    """
    from app.models.company import Company
    from app.services.twilio_service import TwilioService

    data            = request.get_json(silent=True) or {}
    conference_name = (data.get("conference_name") or "").strip()

    if not conference_name:
        return jsonify({"error": "conference_name é obrigatório"}), 400

    item = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)
    if not item:
        return jsonify({"error": "Conferência não encontrada ou já encerrada"}), 404

    if item.get("company_id") and int(item["company_id"]) != g.company_id:
        return jsonify({"error": "Acesso negado"}), 403

    base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        return jsonify({"error": "PUBLIC_BASE_URL não configurado"}), 500

    supervisor_identity = f"supervisor_{g.user_id}"

    # muted=true: supervisor ouve mas não fala; endConferenceOnExit=false: saída não derruba chamada
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response><Dial>'
        f'<Conference'
        f' startConferenceOnEnter="false"'
        f' endConferenceOnExit="false"'
        f' muted="true"'
        f' beep="false"'
        f' participantLabel="{supervisor_identity}"'
        f'>{conference_name}</Conference>'
        '</Dial></Response>'
    )

    try:
        company = Company.query.get(g.company_id)
        svc     = TwilioService.from_company(company, current_user_email=getattr(g, "user_email", None))
        call    = svc.client.calls.create(
            to     = f"client:{supervisor_identity}",
            from_  = svc.twilio_number,
            twiml  = twiml,
        )
        return jsonify({
            "message":          "Entrando na conferência como ouvinte",
            "call_sid":         call.sid,
            "identity":         supervisor_identity,
            "conference_name":  conference_name,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@supervisor_bp.route("/whisper", methods=["POST"])
@require_auth
@require_role("admin", "supervisor")
def whisper():
    """
    Supervisor entra na conferência com muted=false (pode falar com o agente).
    O lead não ouve — usa um participant label separado e Twilio Coach feature.
    Body: { "conference_name": "auto_1_2_abc123", "mode": "whisper" | "barge" }
    - whisper: supervisor fala só com o agente (coach)
    - barge: supervisor entra como participante normal (todos ouvem)
    """
    from app.models.company import Company
    from app.services.twilio_service import TwilioService

    data            = request.get_json(silent=True) or {}
    conference_name = (data.get("conference_name") or "").strip()
    mode            = (data.get("mode") or "whisper").strip()

    if not conference_name:
        return jsonify({"error": "conference_name é obrigatório"}), 400
    if mode not in ("whisper", "barge"):
        return jsonify({"error": "mode deve ser 'whisper' ou 'barge'"}), 400

    item = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)
    if not item:
        return jsonify({"error": "Conferência não encontrada ou já encerrada"}), 404

    if item.get("company_id") and int(item["company_id"]) != g.company_id:
        return jsonify({"error": "Acesso negado"}), 403

    base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        return jsonify({"error": "PUBLIC_BASE_URL não configurado"}), 500

    supervisor_identity = f"supervisor_{g.user_id}"
    # whisper = muted=false, beep=false, endConferenceOnExit=false
    # barge   = muted=false, beep=true,  endConferenceOnExit=false
    muted_val = "false"
    beep_val  = "true" if mode == "barge" else "false"

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response><Dial>'
        f'<Conference'
        f' startConferenceOnEnter="false"'
        f' endConferenceOnExit="false"'
        f' muted="{muted_val}"'
        f' beep="{beep_val}"'
        f' participantLabel="{supervisor_identity}"'
        f'>{conference_name}</Conference>'
        '</Dial></Response>'
    )

    try:
        company = Company.query.get(g.company_id)
        svc     = TwilioService.from_company(company, current_user_email=getattr(g, "user_email", None))
        call    = svc.client.calls.create(
            to     = f"client:{supervisor_identity}",
            from_  = svc.twilio_number,
            twiml  = twiml,
        )
        return jsonify({
            "message":         f"Entrando na conferência em modo {mode}",
            "call_sid":        call.sid,
            "identity":        supervisor_identity,
            "conference_name": conference_name,
            "mode":            mode,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
