import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, g

logger = logging.getLogger(__name__)

from app.auth import require_auth
from app.extensions import db
from app.models.agent import Agent
from app.models.call import Call
from app.models.company import Company
from app.models.lead import Lead
from app.models.callback_queue import CallbackQueue
from app.core.enums import CallbackStatus

operator_workspace_bp = Blueprint(
    "operator_workspace",
    __name__,
    url_prefix="/api/operator/workspace",
)


def _serialize_lead(lead: Lead):
    if not lead:
        return None
    return {
        "id":           lead.id,
        "name":         lead.name,
        "email":        lead.email,
        "company_name": lead.company_name,
        "job_title":    lead.job_title,
        "status":       lead.status,
        "notes":        lead.notes,
        "phones":       lead.get_all_phones(),
        "primary_phone": lead.get_primary_phone(),
    }


def _serialize_call(call: Call):
    if not call:
        return None
    return {
        "id":               call.id,
        "call_sid":         call.call_sid,
        "status":           call.status,
        "direction":        call.direction,
        "phone_dialed":     call.phone_dialed,
        "agent_id":         call.agent_id,
        "lead_id":          call.lead_id,
        "duration_seconds": call.duration_seconds,
        "disposition":      call.disposition,
        "hangup_cause":     call.hangup_cause,
        "created_at":       call.created_at.isoformat() if call.created_at else None,
        "answered_at":      call.answered_at.isoformat() if call.answered_at else None,
        "ended_at":         call.ended_at.isoformat() if call.ended_at else None,
    }


@operator_workspace_bp.route("/<int:agent_id>", methods=["GET"])
@require_auth
def get_operator_workspace(agent_id):
    """
    Retorna o workspace do operador (agente + chamada ativa + lead atual).

    Segurança:
    - Verifica que o agente solicitado pertence ao tenant do usuário logado.
    - A query de calls também é filtrada por company_id para dupla garantia.
    """
    # Um único SELECT já valida a pertença ao tenant
    agent = Agent.query.filter_by(id=agent_id, company_id=g.company_id).first()
    if not agent:
        return jsonify({"error": "operador não encontrado"}), 404

    latest_call = (
        Call.query
        .filter(
            Call.agent_id   == agent_id,
            Call.company_id == g.company_id,  # redundante mas explícito
        )
        .order_by(Call.created_at.desc())
        .first()
    )

    lead = latest_call.lead if latest_call else None

    return jsonify({
        "agent": {
            "id":           agent.id,
            "status":       agent.status,
            "extension":    agent.extension,
            "sip_username": agent.sip_username,
        },
        "current_call": _serialize_call(latest_call),
        "current_lead": _serialize_lead(lead),
    }), 200


@operator_workspace_bp.route("/save_crm", methods=["POST"])
@require_auth
def save_crm():
    """
    Salva o CRM após atendimento.

    Segurança:
    - Agent e Lead são buscados sempre com company_id == g.company_id.
    - Operador da empresa A não consegue salvar dados de leads da empresa B,
      mesmo enviando lead_id ou agent_id de outra empresa no body.
    """
    data = request.get_json(silent=True) or {}

    agent_id      = data.get("agent_id")
    lead_id       = data.get("lead_id")
    call_id       = data.get("call_id")
    qualification = (data.get("qualification") or data.get("disposition") or "").strip()
    notes         = (data.get("notes") or "").strip()
    follow_up     = (data.get("follow_up") or "").strip()
    stage_id      = data.get("stage_id")   # etapa da pipeline selecionada no popup

    if not lead_id:
        return jsonify({"error": "lead_id é obrigatório"}), 400

    # Resolve o agente: prioriza agent_id do body, depois busca pelo user logado
    if agent_id:
        agent = Agent.query.filter_by(id=int(agent_id), company_id=g.company_id).first()
    else:
        # Fallback: agente vinculado ao usuário logado
        from app.models.user import User
        user = User.query.get(g.user_id)
        agent = user.agent_profile if user else None

    # Se ainda não achou agente, cria um temporário em memória (admins sem agente)
    if not agent:
        # Busca qualquer agente da empresa como proxy
        agent = Agent.query.filter_by(company_id=g.company_id).first()

    if not agent:
        return jsonify({"error": "Nenhum operador encontrado para esta empresa"}), 404

    lead = Lead.query.filter_by(id=lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "lead não encontrado"}), 404

    call = None
    if call_id:
        call = Call.query.filter_by(id=call_id, company_id=g.company_id).first()

    timestamp  = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S")
    note_parts = [f"[{timestamp}] Atendimento operador #{agent.id}"]
    if qualification:
        note_parts.append(f"Qualificação: {qualification}")
    if notes:
        note_parts.append(f"Observações: {notes}")
    if follow_up:
        note_parts.append(f"Follow-up: {follow_up}")

    note_block = " | ".join(note_parts)

    if lead.notes and lead.notes.strip():
        lead.notes = f"{lead.notes}\n{note_block}"
    else:
        lead.notes = note_block

    if qualification:
        lead.status = qualification

    if call:
        if qualification:
            call.disposition = qualification
            q_lower = qualification.lower().strip()
            if q_lower in ("voicemail", "caixa_postal", "caixa postal"):
                call.status = "voicemail"
            elif q_lower in ("nao_atendeu", "nao atendeu", "no_answer"):
                call.status = "no_answer"
            elif q_lower in ("numero_invalido", "numero invalido"):
                call.status = "failed"
            elif q_lower in ("busy", "ocupado"):
                call.status = "busy"
        
        if call.status in ["queued", "ringing", "in-progress", "answered_waiting_agent", "agent_joining"]:
            call.status = "completed"  # Fallback apenas se não foi classificado como algo específico acima
        
        if not call.ended_at:
            call.ended_at = datetime.utcnow()

    db.session.flush()

    # Mover deal para etapa selecionada pelo operador no popup
    deal_moved = None
    try:
        from app.models.deal import Deal
        from app.models.pipeline import PipelineStage
        from app.services.crm_service import move_to_stage

        # Se o operador não selecionou um stage específico, tenta deduzir pelo nome da qualification
        if qualification and not stage_id:
            deal_to_check = Deal.query.filter_by(lead_id=lead.id, company_id=g.company_id, status="open").order_by(Deal.created_at.desc()).first()
            if deal_to_check and deal_to_check.pipeline_id:
                qual_lower = qualification.lower().strip()
                # Mapeamento heurístico comum de "qualification" -> "stage name"
                qual_to_stage_map = {
                    "caixa_postal": "caixa postal",
                    "nao_atendeu": "não atendeu",
                    "atendeu": "contato",
                    "reuniao_agendada": "reunião",
                    "ganho": "ganho"
                }
                search_name = qual_to_stage_map.get(qual_lower, qual_lower)
                
                # Busca etapa que contenha o nome na mesma pipeline
                inferred_stage = PipelineStage.query.filter(
                    PipelineStage.pipeline_id == deal_to_check.pipeline_id,
                    db.func.lower(PipelineStage.name).like(f"%{search_name}%")
                ).first()
                if inferred_stage:
                    stage_id = inferred_stage.id
                    logger.info(f"[SAVE_CRM] Etapa deduzida automaticamente para '{search_name}': ID {stage_id}")

        if stage_id:
            target_stage = PipelineStage.query.filter_by(
                id=stage_id, company_id=g.company_id
            ).first()

            if target_stage:
                deal = (
                    Deal.query
                    .filter_by(lead_id=lead.id, company_id=g.company_id, status="open")
                    .order_by(Deal.created_at.desc())
                    .first()
                )
                if deal:
                    move_to_stage(deal, target_stage, triggered_by="agent")
                    deal_moved = {"deal_id": deal.id, "stage": target_stage.name}
    except Exception as e:
        logger.warning(f"[SAVE_CRM] Erro ao mover pipeline: {e}")

    db.session.commit()

    # Determinar próximo passo baseado na disposition
    # REGRAS:
    # - Cx Postal / Não Atendeu / Inválido → próximo NÚMERO do mesmo lead
    # - Atendeu / Qualificação positiva → NÃO avança, lead fica como contactado
    # - Só avança para PRÓXIMO LEAD quando:
    #   1. Todos os números foram tentados (lógica do discador)
    #   2. Operador clica manualmente em "Próximo Lead"
    advance_action = None
    
    if qualification:
        disposition_lower = qualification.lower().strip()
        
        # Se é "caixa postal", "não atendeu" ou "número inválido" → próximo NÚMERO do mesmo lead
        if disposition_lower in ("voicemail", "caixa_postal", "caixa postal", "nao_atendeu", "nao atendeu", 
                              "no_answer", "not answered", "numero_invalido", "numero invalido", "invalid", "invalid_number"):
            advance_action = "next_phone"
        # Se é "atendido" → NÃO avança para próximo lead!
        # O lead foi contactado com sucesso, fica assim.
        # Só avança se o operador clicar manualmente.
    
    # Encerrar chamada ativa no Twilio se houver
    hung_up = False
    # Só ignora se já tiver finalizado de verdade. voicemail, no_answer e failed ainda podem estar na linha.
    if call and call.call_sid and call.status not in ("completed", "canceled"):
        try:
            from app.services.twilio_service import TwilioService
            company = Company.query.get(g.company_id)
            if company:
                svc = TwilioService.from_company(company)
                svc.client.calls(call.call_sid).update(status="completed")
                # Não sobrescreve se for voicemail/no_answer
                if call.status not in ("voicemail", "no_answer", "failed", "busy"):
                    call.status = "completed"
                call.ended_at = datetime.utcnow()
                db.session.commit()
                hung_up = True
                logger.info(f"[SAVE_CRM] Chamada {call.call_sid} encerrada no Twilio")
        except Exception as e_hangup:
            logger.warning(f"[SAVE_CRM] Erro ao encerrar chamada no Twilio: {e_hangup}")
    
    # Limpar estado de memória na bridge após disposição
    try:
        from app.services.call_bridge import ACTIVE_CONFERENCES_BY_AGENT, ACTIVE_CONFERENCES_BY_NAME, clear_pending_conference
        # Localiza pela call_id ou agent_id
        conf_to_clear = None
        if call:
            for item in ACTIVE_CONFERENCES_BY_NAME.values():
                if item.get("db_call_id") == call.id:
                    conf_to_clear = item.get("conference_name")
                    break
            if not conf_to_clear and agent:
                conf_item = ACTIVE_CONFERENCES_BY_AGENT.get(agent.id)
                if conf_item:
                    conf_to_clear = conf_item.get("conference_name")
        if conf_to_clear:
            if conf_to_clear.startswith("agent_bridge_"):
                bridge_item = ACTIVE_CONFERENCES_BY_NAME.get(conf_to_clear)
                if bridge_item:
                    bridge_item["lead_id"]          = None
                    bridge_item["db_call_id"]       = None
                    bridge_item["lead_call_sid"]    = None
                    bridge_item["audio_bridged"]    = False
                    bridge_item["lead_answered_at"] = None
                    bridge_item["status"]           = "idle"
                    ACTIVE_CONFERENCES_BY_NAME.pop(conf_to_clear, None)
                    logger.info(f"[SAVE_CRM] Bridge {conf_to_clear} preservada (dados de lead limpos)")
            else:
                clear_pending_conference(conf_to_clear)
                logger.info(f"[SAVE_CRM] Estado limpo da memória: {conf_to_clear}")
    except Exception as e_mem:
        logger.warning(f"[SAVE_CRM] Erro ao limpar memória: {e_mem}")

    return jsonify({
        "message": "CRM salvo com sucesso",
        "lead": {
            "id":     lead.id,
            "status": lead.status,
            "notes":  lead.notes,
        },
        "call":       _serialize_call(call) if call else None,
        "deal_moved": deal_moved,
        "advance_action": advance_action,
    }), 200


@operator_workspace_bp.route("/join-conference", methods=["POST"])
@require_auth
def join_conference():
    """
    POST /api/operator/workspace/join-conference
    Body: { "agent_id": 1, "conference_name": "auto_1_2_abc123" }

    Fallback: permite ao operador entrar manualmente em uma conferência ativa
    caso o webphone não tenha recebido a chamada automática.

    O sistema usa Twilio REST para fazer uma chamada client:<identity>
    colocando o operador direto na conferência.
    """
    import os
    from app.models.company import Company
    from app.services.twilio_service import TwilioService
    from app.services.call_bridge import ACTIVE_CONFERENCES_BY_NAME

    data = request.get_json(silent=True) or {}

    agent_id        = data.get("agent_id")
    conference_name = (data.get("conference_name") or "").strip()

    if not agent_id:
        return jsonify({"error": "agent_id é obrigatório"}), 400
    if not conference_name:
        return jsonify({"error": "conference_name é obrigatório"}), 400

    # Valida que o agente pertence ao tenant
    agent = Agent.query.filter_by(id=agent_id, company_id=g.company_id).first()
    if not agent:
        return jsonify({"error": "Operador não encontrado"}), 404

    # Verifica se a conference existe em memória
    item = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)
    if not item:
        return jsonify({
            "error": "Conference não encontrada ou já encerrada",
            "conference_name": conference_name,
        }), 404

    # Verifica se o lead ainda está aguardando
    status = item.get("status", "")
    if status not in ("answered_waiting_agent", "calling_agent", "dialing"):
        return jsonify({
            "error": f"Conference não está aguardando operador (status: {status})",
            "conference_name": conference_name,
            "status": status,
        }), 409

    base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        return jsonify({"error": "PUBLIC_BASE_URL não configurado"}), 500

    try:
        company = Company.query.get(g.company_id)
        service = TwilioService.from_company(company)

        # TwiML: operador entra na conference iniciando a sala
        agent_twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Dial>'
            f'<Conference'
            f' startConferenceOnEnter="true"'
            f' endConferenceOnExit="false"'
            f' beep="false"'
            f' participantLabel="agent_{agent_id}"'
            f' statusCallback="{base_url}/api/twilio/conference-events"'
            f' statusCallbackMethod="POST"'
            f' statusCallbackEvent="join leave"'
            f'>{conference_name}</Conference>'
            '</Dial>'
            '</Response>'
        )

        twilio_identity = f"agent_{agent_id}"
        call_result = service.client.calls.create(
            to=f"client:{twilio_identity}",
            from_=service.twilio_number,
            twiml=agent_twiml,
            status_callback=f"{base_url}/api/twilio/status",
            status_callback_event=["answered", "completed"],
            status_callback_method="POST",
        )

        item["status"] = "calling_agent"

        return jsonify({
            "message":     "Chamada enviada para o webphone do operador",
            "call_sid":    call_result.sid,
            "identity":    twilio_identity,
            "conference":  conference_name,
        }), 200

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@operator_workspace_bp.route("/schedule_callback", methods=["POST"])
@require_auth
def schedule_callback():
    """
    Agenda um retorno (callback) para o futuro.
    Body: { "agent_id": 1, "lead_id": 2, "scheduled_for": "2024-05-10T14:30:00", "campaign_id": 5, "call_id": 10 }
    """
    data = request.get_json(silent=True) or {}
    agent_id      = data.get("agent_id")
    lead_id       = data.get("lead_id")
    campaign_id   = data.get("campaign_id")
    call_id       = data.get("call_id")
    scheduled_iso = data.get("scheduled_for")

    if not all([agent_id, lead_id, scheduled_iso]):
        return jsonify({"error": "Parâmetros incompletos (agent_id, lead_id, scheduled_for)"}), 400

    try:
        scheduled_dt = datetime.fromisoformat(scheduled_iso)
    except ValueError:
        return jsonify({"error": "Formato de data inválido. Use ISO8601."}), 400

    # Valida pertença ao tenant
    agent = Agent.query.filter_by(id=agent_id, company_id=g.company_id).first()
    if not agent:
        return jsonify({"error": "Operador não encontrado"}), 404

    lead = Lead.query.filter_by(id=lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    # Cria entrada na fila
    cb = CallbackQueue(
        lead_id=lead_id,
        call_id=call_id or 0,
        campaign_id=campaign_id or lead.campaign_id,
        status=CallbackStatus.PENDING.value,
        scheduled_for=scheduled_dt,
        reserved_agent_id=agent_id
    )
    db.session.add(cb)
    
    # Atualiza status do lead para "retornar" ou similar
    lead.status = "retornar"
    
    db.session.commit()

    return jsonify({
        "message": "Retorno agendado com sucesso",
        "callback_id": cb.id,
        "scheduled_for": cb.scheduled_for.isoformat()
    }), 201


@operator_workspace_bp.route("/skip_phone", methods=["POST"])
@require_auth
def skip_phone():
    """
    Pula para o próximo telefone do lead.
    Marca a chamada atual como no_answer antes de discar o próximo número,
    garantindo que _phones_tried() exclua o número atual corretamente.
    Body: { "agent_id": 1, "lead_id": 2, "campaign_id": 3 }
    """
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    lead_id = data.get("lead_id")
    campaign_id = data.get("campaign_id")  # opcional

    if not all([agent_id, lead_id]):
        return jsonify({"error": "Parâmetros incompletos (agent_id, lead_id)"}), 400

    # Valida pertença ao tenant
    agent = Agent.query.filter_by(id=agent_id, company_id=g.company_id).first()
    if not agent:
        return jsonify({"error": "Agente não encontrado"}), 404

    # Se há campaign_id, usa a lógica completa do discador
    if campaign_id:
        try:
            from app.services.call_bridge import clear_pending_conference, ACTIVE_CONFERENCES_BY_AGENT, ACTIVE_CONFERENCES_BY_NAME
            from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS, dial_next_in_session, _cancel_ring_timer

            sess = AUTO_DIALER_SESSIONS.get(int(campaign_id))

            # 1. Cancela timer de ring
            if sess:
                _cancel_ring_timer(sess)

            # 2. CRÍTICO: marca a chamada ativa como no_answer para que
            #    _phones_tried() a exclua e não repita o mesmo número
            current_call = Call.query.filter(
                Call.lead_id     == lead_id,
                Call.campaign_id == campaign_id,
                Call.status.in_(["ringing", "dialing", "waiting_agent"]),
            ).order_by(Call.created_at.desc()).first()

            if current_call:
                # Cancela no Twilio também
                try:
                    if current_call.call_sid:
                        from app.models.company import Company
                        from app.services.twilio_service import TwilioService
                        company = Company.query.get(g.company_id)
                        if company:
                            svc = TwilioService.from_company(company)
                            svc.client.calls(current_call.call_sid).update(status="completed")
                except Exception as e_tw:
                    logger.warning(f"[SKIP_PHONE] Erro ao cancelar Twilio: {e_tw}")

                current_call.status   = "no_answer"
                current_call.ended_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"[SKIP_PHONE] Chamada {current_call.id} marcada como no_answer")

            # 3. Limpa bridge do agente (preserva agent_leg, limpa dados do lead)
            old_item = ACTIVE_CONFERENCES_BY_AGENT.get(int(agent_id))
            if old_item:
                conf_name = old_item.get("conference_name", "")
                if conf_name.startswith("agent_bridge_"):
                    old_item["lead_id"]          = None
                    old_item["db_call_id"]       = None
                    old_item["lead_call_sid"]    = None
                    old_item["audio_bridged"]    = False
                    old_item["lead_answered_at"] = None
                    old_item["status"]           = "idle"
                    ACTIVE_CONFERENCES_BY_NAME.pop(conf_name, None)
                    logger.info(f"[SKIP_PHONE] Bridge {conf_name} limpa (lead removido, ponte mantida)")
                else:
                    clear_pending_conference(conf_name)
                    logger.info(f"[SKIP_PHONE] Conference {conf_name} limpa")

            # 4. Reseta sessão e disca próximo número
            if sess:
                sess["status"]           = "running"
                sess["current_lead_id"]  = None
                sess["current_call_sid"] = None

            ok, msg = dial_next_in_session(int(campaign_id), g.company_id, force=True)
            logger.info(f"[SKIP_PHONE] Discador automático: ok={ok}, msg={msg}")
            return jsonify({
                "message": "Discando próximo número",
                "ok": ok,
                "msg": msg,
            }), 200
        except Exception as e:
            logger.error(f"[SKIP_PHONE] Erro ao chamar discador: {e}")

    # Fallback: só retorna próximo telefone (lógica antiga)
    lead = Lead.query.filter_by(id=lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    all_phones = lead.get_all_phones()
    current_phone = data.get("current_phone", "")

    next_phone = None
    found_current = False

    for phone in all_phones:
        if found_current:
            next_phone = phone
            break
        if phone == current_phone:
            found_current = True

    return jsonify({
        "message": "Próximo telefone",
        "phone_tried": current_phone,
        "next_phone": next_phone
    }), 200

