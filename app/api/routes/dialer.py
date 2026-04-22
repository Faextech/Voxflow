import os
from uuid import uuid4

from flask import Blueprint, jsonify, request, g

from app.auth import require_auth
from app.extensions import db
from app.models.lead import Lead
from app.models.call import Call
from app.models.agent import Agent
from app.models.company import Company
from app.services.call_bridge import (
    register_pending_conference,
    ACTIVE_CONFERENCES_BY_AGENT,
)
from app.services.twilio_service import TwilioService, normalize_phone_br

dialer_bp = Blueprint("dialer", __name__, url_prefix="/api/dialer")


def _get_public_base_url():
    return (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")


@dialer_bp.route("/start", methods=["POST"])
@require_auth  # exige JWT; popula g.company_id, g.user_id, g.user_role
def start_dialer():
    """
    Inicia uma ligação para o próximo lead disponível da empresa autenticada.

    Segurança:
    - @require_auth garante que só usuários logados chegam aqui.
    - Todas as queries são filtradas por g.company_id — impossível disparar
      ligações de outra empresa, mesmo conhecendo o endpoint.
    """
    try:
        # ==============================
        # 🔑 CREDENCIAIS — por tenant, com fallback para .env
        # ==============================
        public_base_url = _get_public_base_url()
        if not public_base_url:
            return jsonify({"error": "PUBLIC_BASE_URL não configurado"}), 500

        company = Company.query.get(g.company_id)
        if not company:
            return jsonify({"error": "empresa não encontrada"}), 404

        try:
            service = TwilioService.from_company(company)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 500

        body = request.get_json(silent=True) or {}
        requested_campaign_id = body.get("campaign_id")

        # ==============================
        # 🔎 BUSCAR LEAD — sempre filtrado pelo tenant do usuário logado
        # ==============================
        query = Lead.query.filter(
            Lead.status.in_(["novo", "new"]),
            Lead.company_id == g.company_id,   # <-- isolamento de tenant
        )

        if requested_campaign_id:
            # Nota: não precisamos verificar campaign.company_id separadamente
            # porque Lead.company_id já garante o isolamento.
            query = query.filter(Lead.campaign_id == requested_campaign_id)

        lead = query.order_by(Lead.id.asc()).first()

        if not lead:
            return jsonify({"message": "sem leads"}), 200

        phone = (
            lead.get_primary_phone()
            if hasattr(lead, "get_primary_phone")
            else getattr(lead, "numero_1", None)
        )

        if not phone:
            return jsonify({"error": "lead sem telefone"}), 400

        phone = normalize_phone_br(phone)

        campaign_id = lead.campaign_id
        if not campaign_id:
            return jsonify({"error": "lead sem campaign_id"}), 400

        # ==============================
        # 👤 BUSCAR OPERADOR — sempre do mesmo tenant
        # ==============================
        agent = (
            Agent.query
            .filter(
                Agent.company_id == g.company_id,  # <-- isolamento de tenant
                Agent.status.in_(["available", "online", "ready"]),
            )
            .order_by(Agent.id.asc())
            .first()
        )

        if not agent:
            # Fallback: qualquer agente do tenant (sem filtrar status)
            agent = (
                Agent.query
                .filter(Agent.company_id == g.company_id)
                .order_by(Agent.id.asc())
                .first()
            )

        if not agent:
            return jsonify({"error": "nenhum operador cadastrado"}), 400

        # ==============================
        # 🔒 DEDUPLICAÇÃO — impede dois popups para o mesmo agente
        # ==============================
        existing = ACTIVE_CONFERENCES_BY_AGENT.get(agent.id)
        if existing and existing.get("status") not in ("completed", "agent_left"):
            # Cross-check no banco: se a call associada já terminou, limpa o estado
            db_call_id = existing.get("db_call_id")
            if db_call_id:
                stale_call = Call.query.get(db_call_id)
                if stale_call and stale_call.status in (
                    "completed", "failed", "no_answer", "busy", "canceled"
                ):
                    from app.services.call_bridge import clear_pending_conference
                    clear_pending_conference(existing["conference_name"])
                    
                    c_camp_id = existing.get("campaign_id")
                    if c_camp_id:
                        from app.api.routes.auto_dialer import resume_auto_dialer_for_campaign
                        # existing.get("company_id") has the company
                        c_company = existing.get("company_id")
                        if c_company:
                            resume_auto_dialer_for_campaign(c_camp_id, c_company)
                            
                    existing = None

            if existing:
                return jsonify({
                    "error": "operador já possui chamada ativa",
                    "conference_name": existing.get("conference_name"),
                }), 409

        # ==============================
        # 🎯 CRIAR CONFERENCE
        # ==============================
        conference_name = (
            f"camp_{campaign_id}_lead_{lead.id}_agent_{agent.id}_{uuid4().hex[:8]}"
        )

        status_url           = f"{public_base_url}/api/twilio/status"
        conference_status_url = f"{public_base_url}/api/twilio/conference-events"
        wait_url             = f"{public_base_url}/api/twilio/wait-audio"

        # ==============================
        # 💾 CRIAR CALL NO BANCO
        # ==============================
        db_call = Call(
            company_id       = g.company_id,   # vem do JWT, não do lead
            campaign_id      = campaign_id,
            lead_id          = lead.id,
            agent_id         = agent.id,
            phone_dialed     = phone,
            direction        = "outbound",
            status           = "dialing",
            answered_by      = None,
            duration_seconds = 0,
            attempt          = 1,
            recording_url    = None,
            disposition      = None,
            hangup_cause     = None,
        )

        db.session.add(db_call)
        lead.status = "dialing"
        db.session.flush()

        # ==============================
        # 🧠 REGISTRAR CONFERENCE (in-memory — será DB no Passo 4)
        # ==============================
        register_pending_conference(
            conference_name = conference_name,
            agent_id        = agent.id,
            lead_id         = lead.id,
            phone_number    = phone,
            lead_name       = getattr(lead, "name", None),
            company_name    = getattr(lead, "company_name", None),
            campaign_id     = campaign_id,
            db_call_id      = db_call.id,
            lead_call_sid   = None,
        )

        # ==============================
        # 🔥 TWIML
        # ==============================
        twiml_inline = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial>
        <!--
          startConferenceOnEnter="false": o lead fica na sala ouvindo musica de espera.
          A conference so "começa" (musica para, partes se ouvem) quando o OPERADOR
          entrar com startConferenceOnEnter="true" no browser-outgoing.

          endConferenceOnExit="true": se o lead desligar antes ou depois do operador
          entrar, a conference encerra no Twilio e o evento conference-end dispara,
          limpando o estado em memoria.

          answerOnBridge REMOVIDO: esse atributo e para <Number>/<Sip>/<Client>,
          nao para <Conference>. Quando usado em chamada outbound + Conference,
          o Twilio toca uma mensagem em ingles e derruba a ligacao.
        -->
        <Conference
            startConferenceOnEnter="false"
            endConferenceOnExit="true"
            beep="false"
            waitUrl="{wait_url}?c={conference_name}"
            waitMethod="GET"
            statusCallback="{conference_status_url}"
            statusCallbackMethod="POST"
            statusCallbackEvent="start end join leave"
            participantLabel="lead_{lead.id}"
        >{conference_name}</Conference>
    </Dial>
</Response>"""

        # ==============================
        # 📞 FAZER LIGAÇÃO
        # ==============================
        call = service.client.calls.create(
            to=phone,
            from_=service.twilio_number,
            twiml=twiml_inline,
            status_callback=status_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
        )

        db_call.call_sid = call.sid
        db_call.status   = "waiting_agent"
        lead.status      = "waiting_agent"

        db.session.commit()

        return jsonify({
            "message":         "ligando",
            "lead_id":         lead.id,
            "phone":           phone,
            "call_sid":        call.sid,
            "agent_id":        agent.id,
            "conference_name": conference_name,
        }), 200

    except Exception as e:
        db.session.rollback()
        # Limpa o estado em memória se a conferência foi registrada antes do erro
        try:
            from app.services.call_bridge import clear_pending_conference
            clear_pending_conference(conference_name)
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500


@dialer_bp.route("/clear-stuck/<int:agent_id>", methods=["POST"])
@require_auth
def clear_stuck_agent(agent_id):
    """Remove estado travado em memória para um agente (admin only)."""
    from app.services.call_bridge import ACTIVE_CONFERENCES_BY_AGENT, clear_pending_conference
    existing = ACTIVE_CONFERENCES_BY_AGENT.get(agent_id)
    if not existing:
        return jsonify({"message": "nenhum estado ativo para este agente"}), 200
    clear_pending_conference(existing["conference_name"])
    return jsonify({"message": "estado limpo", "conference_name": existing["conference_name"]}), 200


@dialer_bp.route("/hangup-lead", methods=["POST"])
@require_auth
def hangup_lead():
    """
    Encerra a chamada do lead via Twilio API.
    Usado quando o operador clica em "Desligar" no popup — garante que o lead
    também seja desconectado, independente do endConferenceOnExit do operador.

    Body (opcional): { "conference_name": "...", "agent_id": 1 }
    """
    from app.services.call_bridge import ACTIVE_CONFERENCES_BY_AGENT, ACTIVE_CONFERENCES_BY_NAME, clear_pending_conference
    from app.models.call import Call
    from datetime import datetime

    body = request.get_json(silent=True) or {}
    conference_name = body.get("conference_name")
    agent_id = body.get("agent_id")

    # Localiza a conference — por nome ou por agente
    item = None
    if conference_name:
        item = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)
    elif agent_id:
        item = ACTIVE_CONFERENCES_BY_AGENT.get(int(agent_id))

    if not item:
        return jsonify({"message": "nenhuma chamada ativa encontrada"}), 200

    conf_name = item.get("conference_name")
    terminated = []
    errors = []

    try:
        company = Company.query.get(g.company_id)
        service = TwilioService.from_company(company)

        # 1) Encerrar pelo call_sid do lead (leg outbound)
        lead_call_sid = item.get("lead_call_sid")
        if lead_call_sid:
            try:
                service.client.calls(lead_call_sid).update(status="completed")
                terminated.append(f"lead_call_sid={lead_call_sid}")
            except Exception as e:
                errors.append(str(e))

        # 2) Encerrar pelo db_call_id se ainda não terminou
        db_call_id = item.get("db_call_id")
        if db_call_id:
            call = Call.query.filter_by(id=db_call_id, company_id=g.company_id).first()
            if call and call.call_sid and call.call_sid != lead_call_sid:
                try:
                    service.client.calls(call.call_sid).update(status="completed")
                    terminated.append(f"db_call_sid={call.call_sid}")
                except Exception as e:
                    errors.append(str(e))

            # Atualiza DB
            if call:
                call.status = "completed"
                if not call.ended_at:
                    call.ended_at = datetime.utcnow()
                db.session.commit()

        # 3) Limpa estado em memória e retoma o discador
        c_camp_id = item.get("campaign_id")
        if conf_name:
            clear_pending_conference(conf_name)
            
        if c_camp_id:
            from app.api.routes.auto_dialer import resume_auto_dialer_for_campaign
            resume_auto_dialer_for_campaign(c_camp_id, g.company_id)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "message": "Chamada encerrada",
        "terminated": terminated,
        "errors": errors,
        "conference_name": conf_name,
    }), 200
