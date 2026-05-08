import logging
import os
import re
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request, g
from twilio.twiml.voice_response import Dial, VoiceResponse
from twilio.request_validator import RequestValidator

logger = logging.getLogger(__name__)

from app.extensions import db
from app.models.agent import Agent
from app.models.call import Call
from app.models.company import Company
from app.models.lead import Lead
from app.models.callback_queue import CallbackQueue
from app.api.utils.crm_utils import move_lead_to_stage
from app.core.enums import CallbackStatus
from app.services.call_bridge import (
    ACTIVE_CONFERENCES_BY_NAME,
    ACTIVE_CONFERENCES_BY_AGENT,
    clear_pending_conference,
)
from app.services.twilio_service import TwilioService
from app.auth import require_auth

twilio_voice_bp = Blueprint("twilio_voice", __name__, url_prefix="/api/twilio")


def _get_twilio_auth_tokens() -> list[str]:
    """Retorna lista de auth tokens candidatos para validação (empresa + fallback env)."""
    tokens = []
    # Tenta pegar pelo CallSid no banco
    call_sid = request.values.get("CallSid") or request.values.get("call_sid")
    if call_sid:
        try:
            call = Call.query.filter_by(call_sid=call_sid).first()
            if call:
                company = Company.query.get(call.company_id)
                if company:
                    from app.services.twilio_service import TwilioService as _TS
                    svc = _TS.from_company(company)
                    if svc.auth_token:
                        tokens.append(svc.auth_token)
        except Exception:
            pass
    # Fallback: auth token do env
    env_token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    if env_token and env_token not in tokens:
        tokens.append(env_token)
    return tokens


def twilio_webhook(f):
    """
    Decorator que valida a assinatura X-Twilio-Signature antes de processar o webhook.
    Rejeita requests não autenticados com 403.
    Desabilitado via TWILIO_VALIDATE_WEBHOOKS=false (útil em dev/ngrok).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        skip = os.getenv("TWILIO_VALIDATE_WEBHOOKS", "true").lower() in ("false", "0", "no")
        if skip:
            return f(*args, **kwargs)

        signature = request.headers.get("X-Twilio-Signature", "")
        if not signature:
            logger.warning("[TWILIO_SIG] Assinatura ausente em %s — rejeitando", request.path)
            return jsonify({"error": "Forbidden"}), 403

        # URL canônica: usa PUBLIC_BASE_URL se disponível para evitar proxy mismatch
        base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        url  = (base + request.path) if base else request.url
        # Inclui query string quando presente
        if request.query_string:
            url = f"{url}?{request.query_string.decode()}"

        params = dict(request.form) if request.method == "POST" else {}

        auth_tokens = _get_twilio_auth_tokens()
        if not auth_tokens:
            logger.error("[TWILIO_SIG] Nenhum auth_token disponível — rejeitar é mais seguro")
            return jsonify({"error": "Forbidden"}), 403

        valid = False
        for token in auth_tokens:
            try:
                if RequestValidator(token).validate(url, params, signature):
                    valid = True
                    break
            except Exception:
                continue

        if not valid:
            logger.warning("[TWILIO_SIG] Assinatura inválida para %s", request.path)
            return jsonify({"error": "Forbidden"}), 403

        return f(*args, **kwargs)
    return decorated

def update_lead_crm_status(lead_id, call_id, final_status, reason=""):
    """
    Centraliza a classificação do Lead e Call, garantindo regras estritas e logs.
    final_status DEVE ser: "answered", "voicemail", "no_answer", "failed"
    """
    if not lead_id:
        return

    from app.extensions import db
    from app.models.call import Call
    from app.models.lead import Lead
    from app.api.utils.crm_utils import move_lead_to_stage
    import logging
    logger = logging.getLogger(__name__)

    lead = Lead.query.get(lead_id)
    if not lead:
        return

    # Mapeamento do Status pro PIPELINE
    stage_map = {
        "voicemail":       "Caixa Postal",
        "no_answer":       "Não Atendeu",
        "busy":            "Não Atendeu",
        "answered":        "Em Contato",
        "failed":          "Inválido",
        "invalid_number":  "Inválido",
    }
    
    stage = stage_map.get(final_status)
    
    # 1. Atualizar o Call
    if call_id:
        call = Call.query.get(call_id)
        if call:
            call.status = final_status
            call.disposition = reason
            
            # Se já está como caixa postal, e tentar sobrescrever com no_answer, bloquear
            # Regra: Voicemail > Answered > No Answer > Failed
            # Neste helper focamos em atualizar direto mas podemos adicionar lógica futuramente.
            
    # 2. Atualizar o Lead
    lead.status = final_status
    
    logger.info(f"[CRM] Lead {lead_id} -> {final_status} ({stage}) | Motivo: {reason}")
    db.session.commit()
    
    # 3. Mover no funil
    if stage:
        move_lead_to_stage(lead_id, stage)





def _safe_int(value):
    try:
        if value in [None, "", "null", "undefined"]:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_request_value(name, default=None):
    return (
        request.values.get(name)
        or request.form.get(name)
        or request.args.get(name)
        or default
    )


def _get_conference_name_param():
    """Parâmetros enviados pelo Voice SDK em device.connect() (variações de nome)."""
    return (
        _get_request_value("conference_name")
        or _get_request_value("ConferenceName")
        or _get_request_value("ConfName")
        or _get_request_value("conf")
        or _get_request_value("voxflow_conference")
        or _get_request_value("NdConf")
    )


# Salas criadas pelo discador / manual / inbound (fallback se Twilio alterar nomes de parâmetro)
_CONF_ROOM_RE = re.compile(
    r"^(auto_\d+_\d+_[a-f0-9]+|manual_[^_]+_[a-f0-9]+|inbound_[A-Za-z0-9]+|camp_\d+_lead_\d+_agent_\d+_[a-f0-9]+)$",
    re.IGNORECASE,
)


def _infer_conference_name_from_form_scan():
    """Último recurso: achar o nome da sala em qualquer campo do POST."""
    try:
        for _key, val in request.form.items():
            if not val or not isinstance(val, str):
                continue
            s = val.strip()
            if _CONF_ROOM_RE.match(s):
                logger.info(
                    "[TWIML] conference_name inferido por regex no campo %s=%s",
                    _key,
                    s,
                )
                return s
    except Exception as exc:
        logger.debug("infer conference scan: %s", exc)
    return None


def _extract_conference_name_from_request():
    """Nome da conference para device.connect — nunca confie só em um nome de campo."""
    direct = _get_conference_name_param()
    if direct and str(direct).strip():
        return str(direct).strip()
    return _infer_conference_name_from_form_scan()


def _base_url():
    """Tenta ler de PUBLIC_BASE_URL ou usa a URL base da requisição atual."""
    url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not url and request:
        url = request.host_url.rstrip("/")
    return url


@twilio_voice_bp.route("/browser-outgoing", methods=["GET", "POST"])
@twilio_webhook
def browser_outgoing():
    """
    Fluxo de saída do navegador:
    - se vier action=persistent_bridge => criar sala permanente do operador (Estilo Calix)
    - se vier conference_name => entra na conference da chamada aguardando operador
    - se vier To => liga para número real (modo manual)
    """
    to_number = (
        _get_request_value("To")
        or _get_request_value("to")
        or _get_request_value("phone")
    )
    action = _get_request_value("action")
    conference_name = _extract_conference_name_from_request()
    agent_id = _safe_int(
        _get_request_value("agent_id")
        or _get_request_value("AgentId")
        or _get_request_value("aid")
    )
    # lead_id é enviado pelo makeCall() do webphone quando o operador está com um lead ativo
    manual_lead_id = _safe_int(
        _get_request_value("lead_id")
        or _get_request_value("LeadId")
    )

    logger.info(
        "=== /api/twilio/browser-outgoing === method=%s action=%s conference=%s agent_id=%s to=%s",
        request.method,
        action,
        conference_name,
        agent_id,
        to_number,
    )
    logger.debug("[twilio] request.form=%s", dict(request.form))
    logger.debug("[twilio] request.args=%s", dict(request.args))

    response = VoiceResponse()
    base_url = _base_url()

    # ==============================
    # MODO PERSISTENT BRIDGE (Calix-style)
    # ==============================
    if action == "persistent_bridge" or to_number == "bridge":
        agent_conf = f"agent_bridge_{agent_id}"

        # IMPORTANTE: NÃO usar answer_on_bridge em <Dial><Conference> — esse atributo
        # só se aplica a <Number>/<Client>/<Sip> e é ignorado (ou causa comportamento
        # indefinido) com <Conference>. Removê-lo evita que o Twilio tente "bridgear"
        # antes da Conference inicializar e encerre o call leg em ~2s.
        #
        # wait_url OBRIGATÓRIO: sem wait_url o Twilio busca a música padrão via S3
        # (http://), que pode falhar silenciosamente na camada de mídia — gerando um
        # stream sem áudio que o SDK interpreta como conexão morta e dispara BYE.
        # Usando nosso próprio endpoint garante <Pause> determinístico.
        dial = Dial(timeout=86400)
        dial.conference(
            agent_conf,
            # CRÍTICO: endConferenceOnExit=False no agente.
            # Com True, qualquer queda momentânea da ponte WebRTC encerrava toda a
            # conferência. Com False, a conferência sobrevive.
            end_conference_on_exit=False,
            # startConferenceOnEnter=True garante que a sala exista mesmo que o lead 
            # entre primeiro (raro, mas possível).
            start_conference_on_enter=True,
            beep=True,
            wait_url=f"{base_url}/api/twilio/wait-audio?role=agent",
            wait_method="GET",
            status_callback=f"{base_url}/api/twilio/conference-events",
            status_callback_method="POST",
            status_callback_event="start end join leave",
            participant_label=f"agent_{agent_id}",
        )
        response.append(dial)

        # REGISTRO CRÍTICO: Registra a ponte persistente na memória para permitir popups.
        # FIX: Se já houver um lead na ponte (reconexão rápida), preservamos os dados para não fechar o popup.
        from app.services.call_bridge import register_pending_conference, ACTIVE_CONFERENCES_BY_AGENT
        
        current_item = ACTIVE_CONFERENCES_BY_AGENT.get(agent_id)
        existing_lead_id = None
        existing_db_call_id = None
        existing_campaign_id = None
        existing_status = "agent_joined"
        existing_audio_bridged = False
        existing_is_manual = False

        if current_item and current_item.get("lead_id"):
            existing_lead_id = current_item.get("lead_id")
            existing_db_call_id = current_item.get("db_call_id")
            existing_campaign_id = current_item.get("campaign_id")
            existing_status = current_item.get("status", "agent_joined")
            existing_audio_bridged = current_item.get("audio_bridged", False)
            existing_is_manual = current_item.get("is_manual", False)
            logger.info("[BROWSER_OUTGOING] Agente %s reconectando com lead %s ativo. Preservando estado.", agent_id, existing_lead_id)

        register_pending_conference(
            conference_name=agent_conf,
            agent_id=agent_id,
            lead_id=existing_lead_id,
            phone_number="PERSISTENT",
            lead_name="Ponte de Áudio",
            campaign_id=existing_campaign_id
        )

        # Restaurar propriedades extras
        if agent_id in ACTIVE_CONFERENCES_BY_AGENT:
            new_item = ACTIVE_CONFERENCES_BY_AGENT[agent_id]
            if existing_db_call_id:
                new_item["db_call_id"] = existing_db_call_id
                new_item["status"] = existing_status
                new_item["audio_bridged"] = existing_audio_bridged
            if existing_is_manual:
                new_item["is_manual"] = True
        
        logger.info("[BROWSER_OUTGOING] agente %s conectado à ponte persistente %s e registrada com sucesso", agent_id, agent_conf)
        return str(response), 200, {"Content-Type": "text/xml"}


    # ==============================
    # MODO CONFERENCE
    # ==============================
    if conference_name:
        item = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)

        # Se a conference ja foi limpa (lead desligou antes do operador entrar)
        # informa o operador em portugues em vez de entrar numa sala vazia
        if not item:
            response.say(
                "Esta chamada não está mais disponível.",
                language="pt-BR",
            )
            return str(response), 200, {"Content-Type": "text/xml"}

        item["status"] = "agent_joining"
        item["answered_by_agent_at"] = datetime.utcnow().isoformat()

        if item.get("db_call_id"):
            call = Call.query.get(item["db_call_id"])
            if call:
                call.status = "agent_joining"
                db.session.commit()

        logger.info(
            "[BROWSER_OUTGOING] operador entrando na conference=%s agent_id=%s",
            conference_name,
            agent_id,
        )

        # answer_on_bridge=False: para Conference com lead já na sala, o True pode
        # suspender o stream WebRTC aguardando um sinal de "bridge" que chega com
        # delay variável — causando o vácuo de áudio nos primeiros segundos.
        # O áudio instantâneo é garantido pelo resumeTwilioAudioPipeline() no frontend.
        dial = Dial(answer_on_bridge=False, timeout=30)

        dial.conference(
            conference_name,
            start_conference_on_enter=True,
            end_conference_on_exit=False, # Operador sai, lead fica
            beep=False,
            status_callback=f"{base_url}/api/twilio/conference-events",
            status_callback_method="POST",
            status_callback_event="start end join leave",
            participant_label=f"agent_{agent_id or 'unknown'}",
        )
        response.append(dial)

        twiml = str(response)
        logger.debug("TwiML /browser-outgoing conference:")
        logger.debug(twiml)
        return twiml, 200, {"Content-Type": "text/xml"}

    # ==============================
    # MODO MANUAL
    # ==============================
    if not to_number:
        response.say("Número de destino não informado.", language="pt-BR")
        return str(response), 200, {"Content-Type": "text/xml"}

    from uuid import uuid4
    from app.models.company import Company
    from app.services.twilio_service import TwilioService, normalize_phone_br
    from app.services.call_bridge import register_pending_conference

    # Normaliza o número para E.164
    to_number_norm = normalize_phone_br(to_number)
    if not to_number_norm or len(to_number_norm) < 10:
        response.say("Número de telefone inválido.", language="pt-BR")
        return str(response), 200, {"Content-Type": "text/xml"}

    # Cria uma conference temporária para a ligação manual
    conference_name = f"manual_{agent_id or 'x'}_{uuid4().hex[:10]}"

    try:
        # 1) Operador entra na conference com startConferenceOnEnter=true
        dial = Dial(answer_on_bridge=True, timeout=30)
        dial.conference(
            conference_name,
            start_conference_on_enter=True,
            end_conference_on_exit=False,
            beep=False,
            status_callback=f"{base_url}/api/twilio/conference-events",
            status_callback_method="POST",
            status_callback_event="start end join leave",
            participant_label=f"agent_{agent_id or 'manual'}",
        )
        response.append(dial)

        # 2) Disca para o lead via Twilio REST com TwiML que o coloca na mesma conference
        #    startConferenceOnEnter=false para o lead (espera o operador que já está lá)
        lead_twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Dial>'
            f'<Conference'
            f' startConferenceOnEnter="false"'
            f' endConferenceOnExit="true"'
            f' beep="false"'
            f' waitUrl="{base_url}/api/twilio/wait-audio?c={conference_name}"'
            f' waitMethod="GET"'
            f' participantLabel="lead_manual"'
            f'>{conference_name}</Conference>'
            '</Dial>'
            '</Response>'
        )

        # Busca credenciais Twilio
        try:
            if agent_id:
                from app.models.agent import Agent
                from app.models.user import User
                agent = Agent.query.get(agent_id)
                if agent:
                    _usr = User.query.get(agent.user_id) if getattr(agent, "user_id", None) else None
                    _user_email = _usr.email if _usr else None
                    company = Company.query.get(agent.company_id)
                    service = TwilioService.from_company(company, current_user_email=_user_email)
                else:
                    service = TwilioService.from_env(current_user_email=None)
            else:
                service = TwilioService.from_env(current_user_email=None)

            call = service.client.calls.create(
                to=to_number_norm,
                from_=service.twilio_number,
                twiml=lead_twiml,
                status_callback=f"{base_url}/api/twilio/status",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                status_callback_method="POST",
            )

            # Registra conference em memória para rastreamento
            register_pending_conference(
                conference_name=conference_name,
                agent_id=agent_id or 0,
                lead_id=manual_lead_id or 0,
                company_id=getattr(agent, "company_id", None) if agent else None,
                phone_number=to_number_norm,
                lead_name="Ligação Manual",
                campaign_id=None,
                lead_call_sid=call.sid,
            )

            # FIX 5: Mover deal do CRM para "Em Contato" ao iniciar ligação manual
            if manual_lead_id and agent_id:
                try:
                    from app.models.agent import Agent as _Agent
                    _agent = _Agent.query.get(agent_id)
                    _cid = _agent.company_id if _agent else None
                    if _cid:
                        from app.models.deal import Deal
                        from app.models.pipeline import PipelineStage
                        from app.services.crm_service import move_to_stage
                        _deal = (
                            Deal.query
                            .filter_by(lead_id=manual_lead_id, company_id=_cid, status="open")
                            .order_by(Deal.created_at.desc())
                            .first()
                        )
                        if _deal:
                            _stage = (
                                PipelineStage.query
                                .filter(
                                    PipelineStage.pipeline_id == _deal.pipeline_id,
                                    PipelineStage.company_id  == _cid,
                                    PipelineStage.name.ilike("%em contato%"),
                                )
                                .first()
                            ) or (
                                PipelineStage.query
                                .filter(
                                    PipelineStage.pipeline_id == _deal.pipeline_id,
                                    PipelineStage.company_id  == _cid,
                                    PipelineStage.name.ilike("%liga%"),
                                )
                                .first()
                            )
                            if _stage and _deal.stage_id != _stage.id:
                                move_to_stage(_deal, _stage, triggered_by="manual_dial")
                                db.session.commit()
                except Exception as _crm_err:
                    logger.warning("[MANUAL] CRM move ignorado: %s", _crm_err)

            logger.info(
                "[MANUAL] conference=%s operador=agent_%s to=%s",
                conference_name, agent_id, to_number_norm,
            )

        except Exception as exc:
            logger.error("[MANUAL] erro ao discar lead REST: %s", exc)

    except Exception as exc:
        logger.error("[MANUAL] erro inesperado: %s", exc)
        response = VoiceResponse()
        response.say("Ocorreu um erro ao iniciar a ligação.", language="pt-BR")

    twiml = str(response)
    logger.debug("TwiML /browser-outgoing manual:\n%s", twiml)
    return twiml, 200, {"Content-Type": "text/xml"}



@twilio_voice_bp.route("/amd-hold", methods=["GET", "POST"])
def amd_hold():
    """
    TwiML executado enquanto o AMD analisa a chamada.

    - Mensagem inicial reduz o padrão alô+alô que causa falso-positivo no AMD
      (o AMD analisa apenas o áudio DO lead, então o <Say> não interfere).
    - Suporta mensagem e URL de música customizáveis por campanha via query params.
    - Ao confirmar humano, /amd-callback redireciona via REST para /lead-entry.
    """
    from app.models.campaign import Campaign
    from flask import g

    response = VoiceResponse()

    # Configurações padrão
    hold_message   = "Aguarde, transferindo para um de nossos atendentes."
    hold_music_url = None
    language       = "pt-BR"
    hold_seconds   = 25

    # Tenta carregar configurações customizadas da campanha (passadas como ?cid=)
    campaign_id = request.values.get("cid")
    if campaign_id:
        try:
            camp = Campaign.query.get(int(campaign_id))
            if camp:
                if getattr(camp, "hold_message", None):
                    hold_message = camp.hold_message
                if getattr(camp, "hold_music_url", None):
                    hold_music_url = camp.hold_music_url
                if getattr(camp, "hold_language", None):
                    language = camp.hold_language
        except Exception:
            pass  # Usa defaults se campanha não encontrada

    # Mensagem de abertura (mantém lead engajado, reduz alô+alô)
    response.say(hold_message, language=language, voice="Polly.Camila")

    # Música de espera (se configurada) ou pausa com mensagem periódica
    if hold_music_url:
        response.play(hold_music_url, loop=3)
    else:
        response.pause(length=hold_seconds)
        response.say("Por favor, aguarde. Você será atendido em instantes.", language=language, voice="Polly.Camila")
        response.pause(length=10)

    response.hangup()
    return str(response), 200, {"Content-Type": "text/xml"}


@twilio_voice_bp.route("/wait-audio", methods=["GET", "POST"])
def wait_audio():
    """
    Audio de espera enquanto o lead aguarda o operador.

    - Usa <Say language="pt-BR"> + <Redirect> para loop — sem depender de URL externa.
      Se o waitUrl apontar para nosso servidor e o MP3 externo estiver fora do ar,
      o Twilio cairia no ingles. Com Say+Redirect isso nao acontece.
    - Timeout de 90s: se nenhum operador entrou, encerra com mensagem em portugues.
    - O parametro ?c=<conference_name> e passado pelo waitUrl do dialer para
      identificar qual conference esta esperando.
    """
    response = VoiceResponse()

    # Verificar timeout (lead esperando ha mais de 90s sem operador)
    conference_key = (
        request.values.get("c")
        or request.values.get("conference_name")
    )
    if conference_key:
        item = ACTIVE_CONFERENCES_BY_NAME.get(conference_key)
        if item and item.get("status") == "answered_waiting_agent":
            answered_at_str = item.get("lead_answered_at")
            if answered_at_str:
                try:
                    answered_at = datetime.fromisoformat(answered_at_str)
                    waited_seconds = (datetime.utcnow() - answered_at).total_seconds()
                    if waited_seconds > 90:
                        response.say(
                            "Todos os nossos operadores estão ocupados no momento. "
                            "Por favor, tente novamente em alguns instantes. Obrigado.",
                            language="pt-BR",
                        )
                        response.hangup()
                        return str(response), 200, {"Content-Type": "text/xml"}
                except Exception:
                    pass

    # O cliente pediu silêncio (nenhuma voz "aguarde...").
    # Garante silêncio absoluto. 
    # Em vez de apenas pause, podemos usar um silêncio explícito se necessário,
    # mas Pause 3600 costuma ser suficiente se o TwiML for aceito.
    response.pause(length=3600)
    return str(response), 200, {"Content-Type": "text/xml"}


@twilio_voice_bp.route("/status", methods=["POST"])
@twilio_webhook
def status():
    logger.info("=== /api/twilio/status ===")
    call_sid    = _get_request_value("CallSid")
    call_status = (_get_request_value("CallStatus") or "").strip().lower()

    TERMINAL = {"completed", "failed", "no-answer", "busy", "canceled"}

    # ── Atualiza DB ───────────────────────────────────────────────────────
    call = Call.query.filter_by(call_sid=call_sid).first()
    if call:
        # Não sobrescreve classificações específicas com 'completed' genérico
        if not (call_status == "completed" and call.status in ("voicemail", "no_answer", "failed")):
            if call_status and call_status != call.status:
                if call_status == "in-progress" and call.status == "amd_analyzing":
                    pass
                else:
                    call.status = call_status

        # Gravar answered_at quando a chamada é atendida (in-progress)
        # CRÍTICO: o AMD usa esse timestamp para calcular duração e decidir human/machine
        if call_status == "in-progress" and not call.answered_at:
            call.answered_at = datetime.utcnow()
            logger.info("[STATUS] answered_at gravado para %s às %s", call_sid, call.answered_at)

        if call_status in TERMINAL and not getattr(call, "ended_at", None):
            call.ended_at = datetime.utcnow()
            answered_by  = request.values.get("AnsweredBy")
            final_status = handle_call_status(call_sid, call_status, answered_by)
            update_lead_crm_status(call.lead_id, call.id, final_status, f"webhook/status ({call_status})")

        db.session.commit()

    if call_status not in TERMINAL:
            return "", 204

    req_conf   = request.values.get("c") or request.values.get("conference_name")
    item_found = None
    conf_found = None

    for cname, item in list(ACTIVE_CONFERENCES_BY_NAME.items()):
        if (
            (call and item.get("db_call_id") == call.id)
            or item.get("lead_call_sid") == call_sid
            or req_conf == cname
        ):
            item_found = item
            conf_found = cname
            break

    # Verifica se este call_sid realmente pertence ao bridge encontrado.
    # O match por req_conf==cname é fraco: o mesmo nome agent_bridge_N é reutilizado
    # em chamadas consecutivas do auto-dialer. Um /status tardio da chamada anterior
    # pode encontrar a bridge da chamada nova e apagar os dados do novo lead.
    _is_bridge_owner = item_found and (
        (call and item_found.get("db_call_id") == call.id)
        or item_found.get("lead_call_sid") == call_sid
    )

    if item_found:
        if item_found.get("shifting_to_bridge"):
            return "", 204

        if not _is_bridge_owner:
            logger.info(
                "[STATUS] SID %s não é proprietário do bridge atual (db_call_id=%s, lead_call_sid=%s) — ignorando limpeza",
                call_sid, item_found.get("db_call_id"), item_found.get("lead_call_sid"),
            )
        elif conf_found and conf_found.startswith("agent_bridge_"):
            # Limpa estado do lead na ponte persistente (mantém ponte ativa para agente)
            item_found["status"]           = "agent_joined"
            item_found["lead_id"]          = None
            item_found["db_call_id"]       = None
            item_found["lead_call_sid"]    = None
            item_found["audio_bridged"]    = False
            item_found["lead_answered_at"] = None
            logger.info("[STATUS] Ponte %s: lead removido, ponte do agente mantida", conf_found)
        else:
            clear_pending_conference(conf_found)

    # Avança discador se for chamada do auto-dialer (on_call_ended é idempotente)
    if call and call.campaign_id and call.company_id:
        try:
            from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS, on_call_ended
            _sess = AUTO_DIALER_SESSIONS.get(int(call.campaign_id))
            if _sess and _sess.get("current_call_sid") == call_sid:
                _cancelled = _sess.get("_cancelled_sids") or set()
                if call_sid in _cancelled:
                    _cancelled.discard(call_sid)
                    logger.info("[STATUS] SID %s cancelado manualmente — sem avanço", call_sid)
                else:
                    _disp_map = {
                        "no-answer": "no_answer", "busy": "busy",
                        "failed": "failed", "canceled": "no_answer", "completed": "no_answer",
                    }
                    _disp = _disp_map.get(call_status, "no_answer")
                    _force_advance = False

                    if call.status == "voicemail":
                        _disp = "voicemail"
                    elif call.status == "amd_analyzing" and call_status in ("completed", "canceled", "failed", "no-answer", "busy"):
                        logger.warning("[STATUS] Chamada %s caiu (%s) ANTES do AMD concluir. Race condition detectada.", call_sid, call_status)
                        from app.services import redis_service
                        redis_service.set(f"amd:raced:{call_sid}", "1", ex=60)
                        _disp = "voicemail"
                        _force_advance = True
                    else:
                        # NOVO: Detectar AMD ativo mesmo quando chamada está no /amd-hold
                        # (nessa arquitetura o status nunca é 'amd_analyzing' no DB porque
                        # a chamada não entra na conference — ela fica no Pause do /amd-hold)
                        _item_check = None
                        for _cname, _it in list(ACTIVE_CONFERENCES_BY_NAME.items()):
                            if (
                                (call and _it.get("db_call_id") == call.id)
                                or _it.get("lead_call_sid") == call_sid
                            ):
                                _item_check = _it
                                break

                        _amd_was_active = (
                            call.status in ("dialing", "ringing", "amd_analyzing")
                            or (_item_check and _item_check.get("amd_enabled"))
                        )

                        if _amd_was_active and call_status in ("completed", "canceled", "no-answer", "failed", "busy"):
                            logger.warning(
                                "[STATUS] Chamada %s com AMD ativo terminou (%s) antes do callback (amd-hold arch). Tratando como voicemail.",
                                call_sid, call_status,
                            )
                            from app.services import redis_service
                            redis_service.set(f"amd:raced:{call_sid}", "1", ex=60)
                            _disp = "voicemail"
                            _force_advance = True
                            if call.lead_id:
                                update_lead_crm_status(call.lead_id, call.id, "voicemail", "AMD timeout/call dropped")

                    logger.info("[STATUS] Avançando discador: disposition=%s SID=%s", _disp, call_sid)
                    on_call_ended(int(call.campaign_id), int(call.company_id), call_sid, _disp, delay=0, force_advance=_force_advance)
        except Exception as _e:
            logger.error("[STATUS] Erro ao avançar discador: %s", _e)

    return "", 204


@twilio_voice_bp.route("/amd-callback", methods=["POST"])
@twilio_webhook
def amd_callback():
    """
    Webhook chamado pelo Twilio após análise AMD.
    Melhorias Sprint 7:
    - Usa threshold configurável por campanha (amd_duration_threshold_ms)
    - Respeita unknown_amd_action da campanha (send_to_agent / hangup / retry)
    - Registra amd_duration_ms e amd_result para métricas
    - Emite evento WebSocket ao detectar humano
    - Race condition tratada via Redis TTL 60s
    """
    logger.info("=== /api/twilio/amd-callback ===")
    call_sid        = request.form.get("CallSid")
    answered_by     = (request.form.get("AnsweredBy") or "").strip().lower()
    conference_name = request.values.get("c") or request.values.get("conference_name")

    logger.info("[AMD] CallSid=%s | AnsweredBy=%s | Conf=%s", call_sid, answered_by, conference_name)

    item = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)
    if not item:
        logger.warning("[AMD] Conference %s não encontrada — SID=%s", conference_name, call_sid)
        return "", 204

    campaign_id = item.get("campaign_id")
    company_id  = item.get("company_id")

    # ── Race condition: /status já processou este SID? ────────────────────────
    from app.services import redis_service
    raced_key = f"amd:raced:{call_sid}"
    if redis_service.exists(raced_key):
        redis_service.delete(raced_key)
        logger.info("[AMD] Race condition detectada — SID %s já tratado em /status", call_sid)
        return "", 204

    # ── Carrega chamada do DB ─────────────────────────────────────────────────
    c = Call.query.get(item["db_call_id"]) if item.get("db_call_id") else None

    # Chamada já encerrou antes do AMD retornar → popup fantasma
    if c and getattr(c, "ended_at", None):
        logger.info("[AMD] Chamada %s já encerrou — ignorando AMD tardio", call_sid)
        return "", 204

    # ── Threshold configurável por campanha ───────────────────────────────────
    # Padrão 6000ms. Carrega da campanha se disponível.
    _threshold_ms = 6000
    _unknown_action = "send_to_agent"  # padrão seguro
    if campaign_id:
        try:
            from app.models.campaign import Campaign
            _camp = Campaign.query.get(campaign_id)
            if _camp:
                _threshold_ms   = getattr(_camp, "amd_duration_threshold_ms", None) or 6000
                _unknown_action = getattr(_camp, "unknown_amd_action", None) or "send_to_agent"
        except Exception:
            pass
    _threshold_s = _threshold_ms / 1000.0

    # ── Duração desde atendimento ─────────────────────────────────────────────
    _call_duration = None
    if c and c.answered_at:
        _call_duration = (datetime.utcnow() - c.answered_at).total_seconds()
    _amd_duration_ms = int(_call_duration * 1000) if _call_duration else None

    # ── Classificação AMD ─────────────────────────────────────────────────────
    is_machine = answered_by in (
        "machine_start", "machine_end_beep",
        "machine_end_silence", "machine_end_other", "fax"
    )
    is_uncertain = False

    if answered_by == "unknown":
        # unknown_amd_action configurável por campanha
        if _unknown_action == "hangup":
            is_machine  = True   # trata como máquina → encerra
            answered_by = "machine_end_other"  # normaliza
            logger.info("[AMD] unknown → hangup (campanha configurada)")
        elif _unknown_action == "retry":
            # Marca para retry — trata igual a no_answer
            logger.info("[AMD] unknown → retry (campanha configurada)")
            if c:
                c.amd_result = "unknown"
                c.status     = "no_answer"
                db.session.commit()
            if campaign_id and company_id:
                from app.api.routes.auto_dialer import on_call_ended
                on_call_ended(campaign_id, company_id, call_sid, "no_answer", force_advance=True)
            return "", 200
        else:
            # send_to_agent (padrão) — benefício da dúvida
            is_uncertain = True
            logger.info("[AMD] unknown → send_to_agent (benefício da dúvida)")

    # ── machine_start < threshold → incerto (alô+alô falso positivo) ─────────
    if is_machine and answered_by == "machine_start":
        if _call_duration is None or _call_duration < _threshold_s:
            logger.info(
                "[AMD] machine_start em %.1fs < %.1fs → INCERTO (threshold=%.0fms). "
                "Possível padrão alô+alô. Enviando ao operador.",
                _call_duration or 0, _threshold_s, _threshold_ms,
            )
            is_machine   = False
            is_uncertain = True

    # ── Salva resultado AMD no DB (métricas) ──────────────────────────────────
    if c:
        c.amd_result      = answered_by
        if _amd_duration_ms and hasattr(c, "amd_duration_ms"):
            c.amd_duration_ms = _amd_duration_ms
        db.session.flush()

    if is_machine:
        # ── MÁQUINA CONFIRMADA ────────────────────────────────────────────────
        logger.info("[AMD] ✗ Máquina (%s, %.1fs, threshold=%.1fs) — encerrando SID=%s",
                    answered_by, _call_duration or 0, _threshold_s, call_sid)
        try:
            company = Company.query.get(company_id)
            if company:
                svc = TwilioService.from_company(company, current_user_email=item.get("user_email"))
                svc.client.calls(call_sid).update(status="completed")
        except Exception as e:
            logger.error("[AMD] Erro ao encerrar chamada (máquina): %s", e)

        if c:
            c.status   = "voicemail"
            c.ended_at = c.ended_at or datetime.utcnow()
            db.session.commit()

        update_lead_crm_status(item.get("lead_id"), item.get("db_call_id"), "voicemail", f"AMD: {answered_by}")

        # Emite notificação WebSocket
        try:
            from app.services.socket_service import emit_call_update
            if company_id:
                emit_call_update(company_id, {
                    "call_sid":  call_sid,
                    "amd":       answered_by,
                    "result":    "voicemail",
                    "duration":  _call_duration,
                })
        except Exception:
            pass

        # Enrolar follow-up para voicemail automático (AMD)
        _vm_lead_id = item.get("lead_id")
        if _vm_lead_id and company_id:
            try:
                from app.api.routes.followup_routes import enroll_lead_in_followup
                enroll_lead_in_followup(
                    company_id=company_id,
                    lead_id=_vm_lead_id,
                    campaign_id=campaign_id,
                    call_id=item.get("db_call_id"),
                    disposition="caixa_postal",
                )
            except Exception as _fe:
                logger.debug("[AMD] Erro enroll follow-up voicemail: %s", _fe)

        if campaign_id and company_id:
            item["lead_id"] = item["db_call_id"] = item["lead_call_sid"] = None
            item["status"]  = "idle"
            item["amd_uncertain"] = False
            from app.api.routes.auto_dialer import on_call_ended
            on_call_ended(campaign_id, company_id, call_sid, "voicemail", force_advance=True)

    else:
        # ── HUMANO (ou incerto → operador) ────────────────────────────────────
        logger.info("[AMD] ✓ Humano (%s%.1fs) → redirecionando para conferência %s",
                    "incerto " if is_uncertain else "",
                    _call_duration or 0, conference_name)

        # Redireciona via REST para lead-entry → entra na conference
        try:
            company = Company.query.get(company_id)
            if company:
                svc = TwilioService.from_company(company, current_user_email=item.get("user_email"))
                lead_entry_url = (
                    f"{_base_url()}/api/twilio/lead-entry"
                    f"?c={conference_name}&lead_id={item.get('lead_id', '')}"
                )
                svc.client.calls(call_sid).update(url=lead_entry_url, method="POST")
        except Exception as e:
            logger.error("[AMD] Erro ao redirecionar humano: %s", e)

        _now_iso = datetime.utcnow().isoformat() + "Z"
        item["status"]           = "answered_waiting_agent"
        item["lead_answered_at"] = _now_iso
        item["amd_uncertain"]    = is_uncertain
        if item.get("agent_leg_call_sid"):
            item["audio_bridged"] = True

        if not c and item.get("db_call_id"):
            c = Call.query.get(item["db_call_id"])
        if c:
            c.status      = "answered_waiting_agent"
            c.amd_result  = answered_by
            c.answered_at = c.answered_at or datetime.utcnow()
            if is_uncertain and hasattr(c, "amd_recovered"):
                c.amd_recovered = True   # flag para métricas de falsos positivos
            db.session.commit()

        # Emite evento WebSocket — frontend abre popup imediatamente
        try:
            from app.services.socket_service import emit_call_update
            if company_id:
                emit_call_update(company_id, {
                    "call_sid":   call_sid,
                    "amd":        answered_by,
                    "result":     "human",
                    "uncertain":  is_uncertain,
                    "duration":   _call_duration,
                    "conference": conference_name,
                })
        except Exception:
            pass

        if campaign_id:
            from app.api.routes.auto_dialer import on_lead_answered
            on_lead_answered(campaign_id, call_sid)

    return "", 200


@twilio_voice_bp.route("/conference-events", methods=["GET", "POST"])
@twilio_webhook
def conference_events():
    logger.debug("=== /api/twilio/conference-events ===")

    conference_name   = _get_request_value("FriendlyName")
    event             = (_get_request_value("StatusCallbackEvent") or "").strip().lower()
    participant_label = _get_request_value("ParticipantLabel") or ""
    call_sid          = _get_request_value("CallSid")

    item = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)

    # ── Sem item em memória ─────────────────────────────────────────────────
    if not item:
        return "", 204

    is_lead  = participant_label.startswith("lead_")
    is_agent = participant_label.startswith("agent_")

    # ── participant-join ────────────────────────────────────────────────────
    if event in ("participant-join", "join"):

        if is_lead:
            item["lead_call_sid"] = call_sid

            if item.get("amd_enabled") and item.get("amd_uncertain", True):
                item["status"] = "amd_analyzing"
                logger.info("[CONF] %s → lead entrou (call_sid=%s), mas aguardando AMD", conference_name, call_sid)
                if item.get("db_call_id"):
                    c = Call.query.get(item["db_call_id"])
                    if c:
                        c.status = "amd_analyzing"
                        c.answered_at = c.answered_at or datetime.utcnow()
                        db.session.commit()
            else:
                item["status"] = "answered_waiting_agent"
                # BUG 3 FIX: Não sobrescrever lead_answered_at se já foi setado pelo /amd-callback
                if not item.get("lead_answered_at"):
                    item["lead_answered_at"] = datetime.utcnow().isoformat() + "Z"
                item["amd_uncertain"] = False
                if item.get("agent_leg_call_sid"):
                    item["audio_bridged"] = True

                logger.info("[CONF] %s → lead entrou (call_sid=%s)", conference_name, call_sid)

                if item.get("db_call_id"):
                    c = Call.query.get(item["db_call_id"])
                    if c:
                        c.status      = "answered_waiting_agent"
                        c.answered_at = c.answered_at or datetime.utcnow()
                        db.session.commit()

                # Notifica state machine: lead atendeu → cancela timer, status=in_call
                campaign_id = item.get("campaign_id")
                if campaign_id:
                    from app.api.routes.auto_dialer import on_lead_answered
                    on_lead_answered(campaign_id, call_sid)

        elif is_agent:
            item["status"]             = "agent_joined"
            item["agent_leg_call_sid"] = call_sid
            item["shifting_to_bridge"] = False
            if item.get("lead_id"):
                item["audio_bridged"] = True
            logger.info("[CONF] %s → agente entrou (audio_bridged=%s)", conference_name, item.get("audio_bridged"))

            if item.get("db_call_id"):
                c = Call.query.get(item["db_call_id"])
                if c:
                    c.status = "agent_joined"
                    db.session.commit()

# ── participant-leave ───────────────────────────────────────────────────
    elif event in ("participant-leave", "leave"):

        if is_lead:
            status_at_leave      = item.get("status", "")
            agent_was_connected  = status_at_leave in ("agent_joined", "agent_left", "completed")

            logger.info("[CONF] %s → lead saiu | status_at_leave=%s | agent_conn=%s", 
                      conference_name, status_at_leave, agent_was_connected)

            db_call_id = item.get("db_call_id")  # lê antes de limpar bridge
            if db_call_id:
                c = Call.query.get(db_call_id)
                if c:
                    if agent_was_connected:
                        c.status = "completed"
                    else:
                        # Sem agente = caixa postal / não atendeu:
                        # marca como no_answer para _phones_tried() excluir este número
                        c.status = c.status if c.status in ("voicemail", "no_answer", "failed") else "no_answer"
                    c.ended_at = c.ended_at or datetime.utcnow()
                    db.session.commit()

            # Limpa dados do lead da ponte persistente apenas se o agente NÃO atendeu (ex: caixa postal, desligou antes).
            # Se o agente atendeu, mantemos os dados para que o popup continue aberto e o operador possa classificar a ligação.
            # O /classified do frontend chamará _clear_bridge_for_sid posteriormente.
            if conference_name.startswith("agent_bridge_"):
                if not agent_was_connected:
                    item["lead_id"]          = None
                    item["db_call_id"]       = None
                    item["lead_call_sid"]    = None
                    item["audio_bridged"]    = False
                    item["lead_answered_at"] = None
                    item["status"]           = "idle"
                    logger.info("[CONF] Ponte %s → lead removido imediatamente (agent_was_connected=False)", conference_name)
                else:
                    item["status"]           = "agent_joined"
                    logger.info("[CONF] Ponte %s → lead desligou, mas dados preservados para popup de classificação", conference_name)

            if item.get("shifting_to_bridge"):
                return "", 204

            campaign_id = item.get("campaign_id")
            company_id  = item.get("company_id")

            if not campaign_id or not company_id:
                if db_call_id:
                    _c = Call.query.get(db_call_id)
                    if _c:
                        campaign_id = campaign_id or _c.campaign_id
                        company_id  = company_id  or _c.company_id

            if campaign_id and company_id:
                from app.api.routes.auto_dialer import on_call_ended
                if agent_was_connected:
                    disposition = "answered"
                    delay = None  # usa interval_seconds — popup fica aberto para classificar
                    logger.info("[CONF] Lead saiu (agente conectado) → avançando após intervalo")
                else:
                    disposition = "no_answer"
                    delay = 0  # sem agente → avança imediatamente
                    logger.info("[CONF] Lead saiu (sem agente) → avançando imediatamente")
                on_call_ended(campaign_id, company_id, call_sid, disposition, delay=delay)

        elif is_agent:
            item["status"] = "agent_left"
            logger.debug("[CONF] %s → agente saiu", conference_name)

# ── conference-end ──────────────────────────────────────────────────────
    elif event in ("conference-end", "end"):
        # Ponte persistente: participant-leave do lead já tratou tudo
        if conference_name.startswith("agent_bridge_"):
            logger.info("[CONF-END] Ponte persistente %s — ignorando (tratado em participant-leave)", conference_name)
            return "", 204

        logger.info("[CONF-END] %s encerrou (status=%s)", conference_name, item.get("status"))

        final_status = item.get("status", "")
        was_answered = final_status in ("agent_joined", "agent_left", "completed")

        campaign_id = item.get("campaign_id")
        company_id  = None

        if item.get("db_call_id"):
            c = Call.query.get(item["db_call_id"])
            if c:
                if c.status != "completed":
                    c.status = "completed"
                c.ended_at = c.ended_at or datetime.utcnow()
                company_id = c.company_id
                db.session.commit()

                # Marca callback como completo se aplicável
                if c.lead_id:
                    pending_cb = CallbackQueue.query.filter_by(
                        lead_id=c.lead_id, status=CallbackStatus.DIALING.value
                    ).first()
                    if pending_cb:
                        pending_cb.status = CallbackStatus.COMPLETED.value
                        db.session.commit()

        # Salva gravação
        recording_url = _get_request_value("RecordingUrl")
        if recording_url and item.get("db_call_id"):
            c = Call.query.get(item["db_call_id"])
            if c:
                c.recording_url = recording_url
                db.session.commit()
                lead_id = item.get("lead_id")
                if lead_id:
                    try:
                        from app.models.deal import Deal
                        from app.models.deal_activity import DealActivity
                        deal = Deal.query.filter_by(lead_id=lead_id).first()
                        if deal:
                            db.session.add(DealActivity(
                                deal_id=deal.id, type="call",
                                content="Chamada gravada.",
                                metadata_json={"recording_url": recording_url},
                                created_at=datetime.utcnow(),
                            ))
                            db.session.commit()
                    except Exception:
                        pass

        clear_pending_conference(conference_name)

        if campaign_id and company_id:
            from app.api.routes.auto_dialer import on_call_ended
            disposition = "answered" if was_answered else "no_answer"
            delay       = None if was_answered else 0
            on_call_ended(campaign_id, company_id, call_sid or "", disposition, delay=delay)

    return "", 204


# Mapa de tradução PT-BR para status técnicos da chamada
_CALL_STATUS_PT = {
    "ringing_lead":               "📞 Chamando...",
    "dialing":                   "📲 Discando para o lead...",
    "waiting_webhook":            "⏳ Aguardando sinal da operadora...",
    "awaiting_confirmation":      "🔍 Verificando voz (AMD)...",
    "answered_waiting_agent":     "🎉 Lead atendeu! Conectando...",
    "agent_joining":              "📞 Operador entrando na chamada...",
    "agent_joined":               "📞 Em conversa",
    "agent_left":                 "✍️ Atendimento encerrado",
    "machine_dropped":            "🤖 Caixa postal detectada",
    "completed":                  "✅ Chamada encerrada",
    "no_answer":                  "🔇 Sem resposta",
    "voicemail":                  "📩 Caixa postal",
    "failed":                     "❌ Falha na chamada",
    "call_active":                "📞 Chamada em andamento",
}

def _call_status_display(status: str) -> str:
    return _CALL_STATUS_PT.get(status, status or "—")



@twilio_voice_bp.route("/pending-call/<int:agent_id>", methods=["GET"])
def pending_call(agent_id):
    item = ACTIVE_CONFERENCES_BY_AGENT.get(agent_id)

    if not item:
        return jsonify({"has_call": False, "show_popup": False}), 200

    status = (item.get("status") or "").strip().lower()

    # awaiting_confirmation não é mais usado (AMD desativado) — promover imediatamente
    if status == "awaiting_confirmation":
        item["status"] = "answered_waiting_agent"
        status = "answered_waiting_agent"
        conf_name_val = item.get("conference_name", "")
        if conf_name_val.startswith("agent_bridge_") and item.get("agent_leg_call_sid"):
            item["audio_bridged"] = True

    # Dados básicos para o popup (serão suplementados pelo DB abaixo)
    lead_id = item.get("lead_id")

    # NOVA REGRA A PEDIDO DO CLIENTE:
    # O popup deve abrir e ficar aberto para TODAS as ligações desde o início,
    # mesmo que dê caixa postal, rejeitada ou não atenda,
    # para que o operador possa ler as notas e classificar a ligação manualmente.
    show_popup = lead_id is not None

    # FASE 2: Lógica de Ocultação do Popup (AMD Race Condition)
    # Statuses que NUNCA devem mostrar popup — lead ainda tocando ou AMD analisando.
    # O popup SÓ abre em "answered_waiting_agent" (AMD confirmou humano) ou manual.
    POPUP_HIDDEN_STATUSES = {"queued", "dialing", "ringing", "amd_analyzing", "in-progress", "initiated", "idle", "agent_joined"}
    if item.get("campaign_id") and status in POPUP_HIDDEN_STATUSES:
        show_popup = False

    if show_popup:
        logger.info("[POPUP] Disparando popup para operador %s | Lead %s | Status %s", agent_id, lead_id, status)

    # Persistent Bridge: verifica se a perna do agente ainda está viva via REST API
    # Se o browser fechou/atualizou, o call_sid do agente estará 'completed'.
    # Isso evita o "ghost audio" (popup aberto mas silêncio total).
    agent_leg_sid = item.get("agent_leg_call_sid")
    webphone_connected = False
    if agent_leg_sid:
        try:
            from app.services.twilio_service import TwilioService
            from app.models.company import Company
            agent = Agent.query.get(agent_id)
            if agent:
                company = Company.query.get(agent.company_id)
                service = TwilioService.from_company(company)
                remote_call = service.get_call(agent_leg_sid)
                if remote_call.status in ("in-progress", "ringing", "queued"):
                    webphone_connected = True
        except Exception:
            # Em caso de erro (ex: timeout API), assumimos que está conectado para não bloquear popup
            webphone_connected = True

    # Buscar dados completos do lead no banco para exibir no popup
    lead_data = {}
    lead_id = item.get("lead_id")
    if lead_id:
        from app.models.lead import Lead
        lead = Lead.query.get(lead_id)
        if lead:
            lead_data = {
                "name":         lead.name,
                "email":        lead.email,
                "phone":        lead.numero_1,
                "phone2":       lead.numero_2,
                "company_name": lead.company_name,
                "job_title":    lead.job_title,
                "notes":        lead.notes,
                "status":       lead.status,
                "city":         getattr(lead, "city", None),
                "state":        getattr(lead, "state", None),
            }

    # BUG 1 FIX: Buscar answered_at de múltiplas fontes com fallback pro DB
    _answered_at = item.get("lead_answered_at")
    if not _answered_at and item.get("db_call_id"):
        _db_call_obj = Call.query.get(item["db_call_id"])
        if _db_call_obj and _db_call_obj.answered_at:
            _answered_at = _db_call_obj.answered_at.isoformat() + "Z"
            item["lead_answered_at"] = _answered_at  # cachear em memória

    return jsonify({
        "has_call": bool(lead_id),
        "show_popup": show_popup,
        "status": status,
        "status_display": _call_status_display(status),
        "conference_name": item.get("conference_name"),
        "lead_id": lead_id,
        "call_id": item.get("db_call_id"),
        "campaign_id": item.get("campaign_id"),
        "webphone_connected": webphone_connected,
        "lead": lead_data,
        "audio_bridged": bool(item.get("audio_bridged")),
        "answered_at": _answered_at,
        "is_manual": bool(item.get("is_manual", False)),
    }), 200


@twilio_voice_bp.route("/manual-call", methods=["POST"])
@require_auth
def manual_call():
    """
    Dispara ligação manual conectando o lead à ponte persistente do agente.
    Não usa device.connect() — o agente já está na ponte, só precisa discar o lead via REST.
    """
    from app.models.user import User
    from app.services.call_bridge import register_pending_conference
    from app.services.twilio_service import normalize_phone_br

    data = request.get_json(force=True) or {}
    agent_id = _safe_int(data.get("agent_id"))
    to_number = (data.get("to") or data.get("phone") or "").strip()
    lead_id = _safe_int(data.get("lead_id"))

    if not agent_id:
        return jsonify({"error": "agent_id obrigatório"}), 400
    if not to_number:
        return jsonify({"error": "Número de destino obrigatório"}), 400

    to_norm = normalize_phone_br(to_number)
    if not to_norm or len(to_norm) < 10:
        return jsonify({"error": "Número de telefone inválido"}), 400

    agent = Agent.query.filter_by(id=agent_id, company_id=g.company_id).first()
    if not agent:
        return jsonify({"error": "Operador não encontrado"}), 404

    company = Company.query.get(g.company_id)
    try:
        service = TwilioService.from_company(company, current_user_email=getattr(g, "user_email", None))
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

    conf_name = f"agent_bridge_{agent_id}"
    base_url = _base_url()
    conf_url = f"{base_url}/api/twilio/conference-events"
    status_url = f"{base_url}/api/twilio/status"

    lead_twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response><Dial>'
        f'<Conference'
        f' startConferenceOnEnter="true"'
        f' endConferenceOnExit="true"'
        f' beep="false"'
        f' participantLabel="lead_manual"'
        f' statusCallback="{conf_url}"'
        f' statusCallbackMethod="POST"'
        f' statusCallbackEvent="join leave"'
        f'>{conf_name}</Conference>'
        '</Dial></Response>'
    )

    try:
        call = service.client.calls.create(
            to=to_norm,
            from_=service.twilio_number,
            twiml=lead_twiml,
            status_callback=f"{status_url}?c={conf_name}",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
        )
    except Exception as exc:
        logger.error("[MANUAL-CALL] erro ao discar %s: %s", to_norm, exc)
        return jsonify({"error": f"Erro ao discar: {exc}"}), 500

    register_pending_conference(
        conference_name=conf_name,
        agent_id=agent_id,
        lead_id=lead_id or 0,
        company_id=g.company_id,
        phone_number=to_norm,
        lead_name="Ligação Manual",
        campaign_id=None,
        lead_call_sid=call.sid,
        user_email=getattr(g, "user_email", None),
    )

    # Marca explicitamente como chamada manual para o frontend rotear o popup correto
    if conf_name in ACTIVE_CONFERENCES_BY_NAME:
        ACTIVE_CONFERENCES_BY_NAME[conf_name]["is_manual"] = True
        ACTIVE_CONFERENCES_BY_NAME[conf_name]["audio_bridged"] = True

    logger.info("[MANUAL-CALL] agent=%s to=%s conf=%s sid=%s", agent_id, to_norm, conf_name, call.sid)
    return jsonify({"ok": True, "call_sid": call.sid, "conference": conf_name}), 200


@twilio_voice_bp.route("/end-bridge/<int:agent_id>", methods=["POST"])
def end_bridge(agent_id):
    """
    Encerra a Persistent Bridge do agente via REST API do Twilio.
    Chamado quando o operador clica 'Desligar' ou fecha o browser (beforeunload).
    Como a conferência usa endConferenceOnExit=False, ela não se encerra
    automaticamente quando o WebRTC cai — precisamos encerrá-la explicitamente.
    """
    try:
        agent = Agent.query.get(agent_id)
        if not agent:
            return jsonify({"error": "Agente não encontrado"}), 404

        company = Company.query.get(agent.company_id)
        if not company:
            return jsonify({"error": "Empresa não encontrada"}), 404

        from app.services.call_bridge import ACTIVE_CONFERENCES_BY_AGENT
        item = ACTIVE_CONFERENCES_BY_AGENT.get(agent_id) or {}
        service = TwilioService.from_company(company, current_user_email=item.get("user_email") or getattr(g, 'user_email', None))
        agent_conf = f"agent_bridge_{agent_id}"

        # Busca a conferência pelo friendly name e encerra
        conferences = service.client.conferences.list(
            friendly_name=agent_conf, status="in-progress", limit=5
        )
        ended = 0
        for conf in conferences:
            try:
                service.client.conferences(conf.sid).update(status="completed")
                ended += 1
                logger.info("[END_BRIDGE] Conferência %s (%s) encerrada para agente %s", agent_conf, conf.sid, agent_id)
            except Exception as exc:
                logger.warning("[END_BRIDGE] Erro ao encerrar conferência %s: %s", conf.sid, exc)

        # Limpa estado em memória do agente
        if agent_id in ACTIVE_CONFERENCES_BY_AGENT:
            conf_name = ACTIVE_CONFERENCES_BY_AGENT[agent_id].get("conference_name")
            if conf_name:
                clear_pending_conference(conf_name)

        return jsonify({"ok": True, "conferences_ended": ended}), 200

    except Exception as exc:
        logger.error("[END_BRIDGE] Erro inesperado: %s", exc)
        return jsonify({"error": str(exc)}), 500


@twilio_voice_bp.route("/debug/agent-state/<int:agent_id>", methods=["GET"])
def debug_agent_state(agent_id):
    """Diagnóstico: mostra estado atual do agente em memória (dev only)."""
    item = ACTIVE_CONFERENCES_BY_AGENT.get(agent_id)
    public_base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip()
    return jsonify({
        "agent_id":       agent_id,
        "conference":     item,
        "public_base_url": public_base_url,
        "all_conferences": list(ACTIVE_CONFERENCES_BY_NAME.keys()),
    }), 200


@twilio_voice_bp.route("/amd-reclassify/<int:call_id>", methods=["POST"])
@require_auth
def amd_reclassify(call_id):
    """
    FASE 3: Permite ao supervisor reclassificar uma chamada que o AMD errou.
    Ações:
    - 'retry_now'         → coloca o lead de volta na fila como próximo (máxima prioridade)
    - 'retry_end'         → coloca o lead no final da fila da campanha
    - 'confirm_voicemail' → confirma como caixa postal definitiva (sem retry)
    """
    data   = request.get_json(force=True) or {}
    action = data.get("action")  # retry_now | retry_end | confirm_voicemail

    call = Call.query.get(call_id)
    if not call or call.company_id != g.company_id:
        return jsonify({"error": "Chamada não encontrada"}), 404

    lead = Lead.query.get(call.lead_id)
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    if action == "retry_now":
        lead.status       = "retry"
        call.amd_recovered = True
        db.session.commit()
        # Se a campanha estiver rodando, forçar esse lead como próximo
        from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS
        sess = AUTO_DIALER_SESSIONS.get(int(call.campaign_id))
        if sess:
            sess["_priority_lead_id"] = lead.id
        logger.info("[AMD-RECLASSIFY] Lead %s recolocado como PRÓXIMO (retry_now)", lead.id)
        return jsonify({"ok": True, "message": "Lead recolocado como próximo na fila"}), 200

    elif action == "retry_end":
        lead.status        = "retry"
        call.amd_recovered = True
        db.session.commit()
        logger.info("[AMD-RECLASSIFY] Lead %s recolocado no FINAL da fila (retry_end)", lead.id)
        return jsonify({"ok": True, "message": "Lead recolocado no final da fila"}), 200

    elif action == "confirm_voicemail":
        lead.status       = "voicemail"
        call.status       = "voicemail"
        call.amd_result   = "confirmed_voicemail"
        call.amd_recovered = True
        db.session.commit()
        update_lead_crm_status(lead.id, call.id, "voicemail", "Supervisor confirmou caixa postal")
        logger.info("[AMD-RECLASSIFY] Lead %s confirmado como caixa postal pelo supervisor", lead.id)
        return jsonify({"ok": True, "message": "Confirmado como caixa postal"}), 200

    return jsonify({"error": "Ação inválida. Use: retry_now, retry_end ou confirm_voicemail"}), 400


@twilio_voice_bp.route("/lead-entry", methods=["POST"])
@twilio_webhook
def lead_entry():
    """
    Portão de Áudio Instantâneo (0ms delay):
    O lead é jogado diretamente na conferência ao atender.
    O AMD (Detecção de Máquina) roda em paralelo.
    """
    conference_name = request.values.get("c")
    lead_id = request.values.get("lead_id")
    
    response = VoiceResponse()
    
    if not conference_name:
        logger.warning("[LEAD-ENTRY] Tentativa de entrada sem conference_name. Dando pause de segurança.")
        response.pause(length=10)
        return str(response), 200, {"Content-Type": "text/xml"}

    dial = Dial()
    public_base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    status_callback_url = f"{public_base_url}/api/twilio/conference-events" if public_base_url else "/api/twilio/conference-events"

    dial.conference(
        conference_name,
        start_conference_on_enter=True,
        end_conference_on_exit=True,
        beep=False,
        participant_label=f"lead_{lead_id}" if lead_id else None,
        status_callback=status_callback_url,
        status_callback_method="POST",
        status_callback_event="join leave"
    )
    response.append(dial)
    
    logger.info("[LEAD-ENTRY] Lead %s entrando IMEDIATAMENTE na conferência %s", lead_id, conference_name)
    return str(response), 200, {"Content-Type": "text/xml"}


@twilio_voice_bp.route("/lead-to-bridge", methods=["POST"])
@twilio_webhook
def lead_to_bridge():
    """
    Acionado via REST API Redirect quando o AMD confirma Humano.
    Este é o momento real em que o lead entra na conferência.
    """
    conference_name = request.values.get("c")
    lead_id = request.values.get("lead_id")
    
    response = VoiceResponse()
    dial = Dial()
    public_base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    status_callback_url = f"{public_base_url}/api/twilio/conference-events" if public_base_url else "/api/twilio/conference-events"
    
    dial.conference(
        conference_name,
        start_conference_on_enter=True,
        end_conference_on_exit=True,
        beep=False,
        participant_label=f"lead_{lead_id}" if lead_id else None,
        status_callback=status_callback_url,
        status_callback_method="POST",
        status_callback_event="join leave"
    )
    response.append(dial)
    return str(response), 200, {"Content-Type": "text/xml"}


@twilio_voice_bp.route("/voice", methods=["GET", "POST"])
@twilio_webhook
def voice():
    logger.info("=== /api/twilio/voice chamado ===")
    from_ph = (_get_request_value("From") or "").strip()
    to_ph = (_get_request_value("To") or "").strip()
    call_sid = _get_request_value("CallSid") or ""

    # device.connect() do Voice SDK usa From=client:agent_X. Se o TwiML App na
    # Twilio Console apontar para /voice em vez de /browser-outgoing, sem este
    # repasse o operador recebe o TwiML de inbound e entra em outra conferência
    # (inbound_*) — o lead fica em auto_* / dial_*: silêncio total.
    if from_ph.startswith("client:"):
        # Persistent Bridge: action=persistent_bridge não carrega conference_name nem To,
        # por isso precisa de verificação explícita antes do scan genérico.
        action_param = _get_request_value("action")
        if action_param == "persistent_bridge":
            logger.info(
                "[VOICE] TwiML App → repassando para browser_outgoing (action=persistent_bridge). "
                "Configure o Voice URL do TwiML App como .../api/twilio/browser-outgoing",
            )
            return browser_outgoing()
        conf_param = _extract_conference_name_from_request()
        if conf_param:
            logger.info(
                "[VOICE] TwiML App → repassando para browser_outgoing (conference=%s). "
                "Configure o Voice URL do TwiML App como .../api/twilio/browser-outgoing",
                conf_param,
            )
            return browser_outgoing()
        if to_ph and not to_ph.lower().startswith("client:"):
            logger.info(
                "[VOICE] TwiML App → repassando para browser_outgoing (To=%s)",
                to_ph,
            )
            return browser_outgoing()

    # Identifica a empresa pelo número chamado (To)
    from app.services.twilio_service import normalize_phone_br
    to_ph_norm = normalize_phone_br(to_ph)
    company = Company.query.filter_by(twilio_number=to_ph_norm).first()
    
    if not company:
        # Fallback para o Master (Allan) se não encontrar a empresa pelo número
        company = Company.query.get(1)

    company_id = company.id if company else 1
    
    # Identifica o primeiro agente disponível da empresa para receber a chamada inbound
    # Em um fluxo real, isso usaria uma fila ou regra de roteamento
    agent = Agent.query.filter_by(company_id=company_id, status='active').first()
    agent_id = agent.id if agent else 1
    
    conf_name = f"agent_bridge_{agent_id}"
    public_base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip()
    if not public_base_url:
        public_base_url = _base_url()
        
    conf_url = f"{public_base_url}/api/twilio/conference-events"
    
    # 1. Registrar a state da conferência INBOUND
    from app.services.call_bridge import register_pending_conference
    
    register_pending_conference(
        conference_name=conf_name,
        agent_id=agent_id,
        lead_id=0,
        company_id=company_id,
        phone_number=from_ph,
        lead_name="Ligação Receptiva",
        campaign_id=None,
        lead_call_sid=call_sid,
        user_email=None,
    )
    
    if conf_name in ACTIVE_CONFERENCES_BY_NAME:
        ACTIVE_CONFERENCES_BY_NAME[conf_name]["audio_bridged"] = True

    # Não disparamos client:agent_* — o operador entra com device.connect (outgoing)
    # para o mesmo conference_name quando o pending-call aparecer no browser.

    # Retorna o TwiML pro Cliente que ligou entrar na conferência e esperar
    response = VoiceResponse()
    dial = Dial()
    dial.conference(
        conf_name,
        start_conference_on_enter=False,
        end_conference_on_exit=True,
        beep=True,
        wait_url=f"{public_base_url}/api/twilio/wait-audio?c={conf_name}",
        status_callback=conf_url,
        status_callback_method="POST",
        status_callback_event="start end join leave",
        participant_label="inbound_caller"
    )
    response.append(dial)
    
    return str(response), 200, {"Content-Type": "text/xml"}


def handle_call_status(call_sid, call_status, answered_by=None):
    """
    Mapeia status do Twilio para classificação CRM.
    Ordem de prioridade estrita:
      1. AMD confirmou máquina → voicemail
      2. completed + duração > 3s → answered
      3. completed curta (drop/voicemail rápido) → no_answer
      4. no-answer / canceled → no_answer
      5. failed → failed
      6. busy → busy (linha ocupada — NÃO é voicemail)
    """
    # 1. AMD explicitou voicemail
    if answered_by and 'machine' in answered_by.lower():
        return 'voicemail'

    # 2/3. Chamada completada
    if call_status == 'completed':
        call = Call.query.filter_by(call_sid=call_sid).first()
        # Se já foi classificado pelo AMD ou fluxo anterior, preserva
        if call and call.status in ('voicemail', 'answered', 'no_answer', 'busy', 'failed'):
            return call.status
        if call and getattr(call, "duration_seconds", 0) > 3:
            return 'answered'
        return 'no_answer'

    # 4. Sem resposta
    if call_status in ('no-answer', 'no_answer', 'canceled'):
        return 'no_answer'

    # 5. Falha técnica
    if call_status == 'failed':
        return 'failed'

    # 6. Ocupado (linha ocupada — cliente pode chamar de volta)
    if call_status == 'busy':
        return 'busy'

    return 'no_answer'  # fallback seguro


@twilio_voice_bp.route("/client-status", methods=["GET", "POST"])
@twilio_webhook
def client_status():
    logger.debug("=== /api/twilio/client-status ===")
    logger.debug("[twilio] method = %s", request.method)
    logger.debug("[twilio] request.values = %s", dict(request.values))
    return "", 204


@twilio_voice_bp.route("/bridge-action", methods=["GET", "POST"])
@twilio_webhook
def bridge_action():
    logger.debug("=== /api/twilio/bridge-action ===")
    logger.debug("[twilio] method = %s", request.method)
    logger.debug("[twilio] request.values = %s", dict(request.values))
    return "", 204