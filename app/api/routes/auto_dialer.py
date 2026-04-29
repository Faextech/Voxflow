"""
Discador Automático — VoxFlow

Estados:
  running  → entre chamadas, buscando próximo lead
  ringing  → chamada criada, aguardando atender (timeout 50s)
  in_call  → lead atendeu, popup aberto, operador ativo
  paused   → pausado manualmente
  stopped  → parado manualmente
  finished → todos os leads percorridos

Fluxo por chamada:
  dial_next_in_session() → ringing
  lead atende → on_lead_answered() → in_call (timer cancelado)
  lead desliga → on_call_ended() → running → _advance() → dial_next
  timeout 50s  → on_call_ended() → running → _advance() → dial_next
"""
import logging
import os
import threading
import time
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.auth import require_auth
from app.extensions import db
from app.models.agent import Agent
from app.models.call import Call
from app.models.campaign import Campaign
from app.models.company import Company
from app.models.lead import Lead
from app.models.callback_queue import CallbackQueue
from app.core.enums import CallbackStatus
from app.services.call_bridge import (
    ACTIVE_CONFERENCES_BY_AGENT,
    clear_pending_conference,
    register_pending_conference,
    update_pending_lead_call_sid,
)
from app.services.twilio_service import TwilioService, normalize_phone_br, InsufficientCreditError

logger = logging.getLogger(__name__)

auto_dialer_bp = Blueprint("auto_dialer", __name__, url_prefix="/api/dialer/auto")

AUTO_DIALER_SESSIONS: dict = {}

_STATUS_DISPLAY = {
    "running":  "▶ Discando...",
    "ringing":  "📞 Chamando...",
    "in_call":  "📞 Em conversa",
    "paused":   "⏸ Pausado",
    "stopped":  "⏹ Parado",
    "finished": "✅ Finalizado",
}


# ── Session factory ───────────────────────────────────────────────────────────

def _new_session(campaign_id, company_id, campaign_name, interval_sec, leads_total, mobile_only=False, user_email=None):
    return {
        "status":               "running",
        "campaign_id":          campaign_id,
        "company_id":           company_id,
        "campaign_name":        campaign_name,
        "user_email":           user_email,
        "interval_seconds":     interval_sec,
        "leads_total":          leads_total,
        "leads_done":           0,
        "current_lead_id":      None,
        "current_lead_name":    None,
        "current_lead_phone":   None,
        "current_lead_company": None,
        "started_at":           datetime.utcnow().isoformat(),
        "mobile_only":          mobile_only,
        # internal — not serialized
        "_lock":           threading.Lock(),
        "_ring_timer":     None,
        "_cancelled_sids": set(),
        "current_call_sid": None,
    }


def _session_for_json(s: dict) -> dict:
    if not s:
        return {}
    skip = {"_lock", "_ring_timer", "_cancelled_sids", "_amd_raced_sids"}
    return {k: v for k, v in s.items() if k not in skip}


# ── Utilities ─────────────────────────────────────────────────────────────────

def _get_public_base_url() -> str:
    url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not url:
        try:
            url = request.host_url.rstrip("/")
        except Exception:
            pass
    return url


def _get_app():
    from flask import current_app
    try:
        return current_app._get_current_object()
    except RuntimeError:
        from app import create_app
        return create_app()


def is_mobile_br(phone: str) -> bool:
    if not phone:
        return False
    n = normalize_phone_br(phone)
    if not n or not n.startswith("+55"):
        return True
    sub = n[3:]
    if len(sub) == 11:
        return sub[2] == "9"
    if len(sub) == 10:
        return False
    return True


def _phones_tried(lead_id, campaign_id, company_id, since=None) -> set:
    q = Call.query.filter(
        Call.lead_id     == lead_id,
        Call.campaign_id == campaign_id,
        Call.company_id  == company_id,
        Call.phone_dialed.isnot(None),
        Call.status != "reset",
    )
    # IGNORA o 'since' para que NUNCA repita telefones já tentados (mesmo após pausar/retomar)
    return {normalize_phone_br(c.phone_dialed) for c in q.all() if c.phone_dialed}


def _next_phone_for_lead(lead, campaign_id, company_id, since=None, mobile_only=False, ignore_history=False):
    if ignore_history:
        tried = set()
    else:
        tried = _phones_tried(lead.id, campaign_id, company_id, since=since)
    logger.info("[PHONE] _next_phone_for_lead: lead=%s, phones=%s, tried=%s, ignore_history=%s", lead.id, lead.get_all_phones(), tried, ignore_history)
    for raw in lead.get_all_phones():
        raw = str(raw).strip()
        if raw.endswith(".0"):
            raw = raw[:-2]
        norm = normalize_phone_br(raw)
        if mobile_only and not is_mobile_br(norm):
            continue
        if norm not in tried:
            logger.info("[PHONE] Lead=%s → próximo número: %s (não tentado)", lead.id, norm)
            return norm
    logger.info("[PHONE] Lead=%s → todos os números tentados", lead.id)
    return None


def _next_lead_query(campaign_id, company_id, exclude_ids):
    target = [
        "new", "novo", "tentativa", "tentando", "retry", "callback", "retornar", "qualified",
        "no_answer", "busy", "failed", "voicemail", "invalid_number"
    ]
    q = Lead.query.filter(
        Lead.campaign_id == campaign_id,
        Lead.company_id  == company_id,
        Lead.status.in_(target),
    )
    if exclude_ids:
        q = q.filter(Lead.id.notin_(exclude_ids))
    return q.order_by(Lead.import_order.asc(), Lead.id.asc()).first()


# ── Bridge helpers ────────────────────────────────────────────────────────────

def _cancel_twilio_call(company_id, call_sid):
    try:
        company = Company.query.get(company_id)
        if company:
            sess = AUTO_DIALER_SESSIONS.get(int(getattr(request, 'form', {}).get('campaign_id', 0))) or {}
            email = sess.get("user_email")
            svc = TwilioService.from_company(company, current_user_email=email)
            svc.client.calls(call_sid).update(status="completed")
            logger.info("[DIALER] Chamada %s encerrada no Twilio", call_sid)
    except Exception as e:
        logger.warning("[DIALER] Erro ao cancelar %s: %s", call_sid, e)


def _clear_bridge_for_sid(call_sid: str):
    """Limpa estado de memória da ponte para o SID informado."""
    for item in list(ACTIVE_CONFERENCES_BY_AGENT.values()):
        if item.get("lead_call_sid") == call_sid:
            conf = item.get("conference_name", "")
            if conf.startswith("agent_bridge_"):
                item["status"]           = "agent_joined"
                item["lead_id"]          = None
                item["db_call_id"]       = None
                item["lead_call_sid"]    = None
                item["audio_bridged"]    = False
                item["lead_answered_at"] = None
            else:
                clear_pending_conference(conf)
            logger.info("[BRIDGE] Estado limpo para SID %s (conf=%s)", call_sid, conf)
            return


# ── Ring timer ────────────────────────────────────────────────────────────────

def _cancel_ring_timer(sess: dict):
    t = sess.get("_ring_timer")
    if isinstance(t, threading.Timer) and t.is_alive():
        t.cancel()
    sess["_ring_timer"] = None


def _start_ring_timer(campaign_id: int, company_id: int, call_sid: str, sess: dict):
    app = _get_app()

    def _fire():
        logger.info("[TIMEOUT] 50s expirou para %s — encerrando chamada", call_sid)
        with app.app_context():
            s = AUTO_DIALER_SESSIONS.get(campaign_id)
            if not s:
                return
            if s.get("current_call_sid") != call_sid:
                logger.info("[TIMEOUT] SID %s não é mais o atual — ignorando", call_sid)
                return
            if s.get("status") not in ("ringing", "running"):
                logger.info("[TIMEOUT] Status=%s — timeout ignorado", s.get("status"))
                return

            s["_ring_timer"] = None
            _cancel_twilio_call(company_id, call_sid)

            call = Call.query.filter_by(call_sid=call_sid).first()
            if call:
                call.status   = "no_answer"
                call.ended_at = datetime.utcnow()
                lead = Lead.query.get(call.lead_id)
                if lead and lead.status == "dialing":
                    lead.status = "no_answer"
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            _clear_bridge_for_sid(call_sid)
            on_call_ended(campaign_id, company_id, call_sid, "no_answer", delay=0)

    timer = threading.Timer(50, _fire)
    timer.daemon = True
    timer.name   = f"RingTimer-{campaign_id}"
    timer.start()
    sess["_ring_timer"] = timer
    logger.info("[TIMER] Timeout de 50s agendado para campaign=%s SID=%s", campaign_id, call_sid)


# ── Event API (chamados pelos webhooks em twilio_voice.py) ───────────────────

def on_lead_answered(campaign_id: int, call_sid: str):
    """
    Lead atendeu e entrou na conference.
    Cancela o ring timer e muda para in_call.
    """
    campaign_id = int(campaign_id)
    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess:
        return

    if sess.get("current_call_sid") != call_sid:
        logger.info("[EVENT] on_lead_answered: SID %s não é o atual — ignorando", call_sid)
        return

    _cancel_ring_timer(sess)
    sess["status"] = "in_call"
    logger.info("[EVENT] Lead atendeu (SID=%s) — status=in_call, timer cancelado", call_sid)


def on_call_ended(campaign_id: int, company_id: int, call_sid: str, disposition: str, delay: int = None, force_advance: bool = False):
    """
    Chamada encerrada por qualquer motivo (timeout, desligou, no-answer, busy, failed).
    Limpa estado e agenda próxima discagem.
    """
    campaign_id = int(campaign_id)
    company_id  = int(company_id)

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess:
        logger.warning("[EVENT] on_call_ended: sessão não encontrada")
        return

    logger.info("[EVENT] on_call_ended: campaign=%s, sid=%s, disposition=%s, status=%s", 
              campaign_id, call_sid, disposition, sess.get("status"))

    if sess.get("status") in ("paused", "stopped", "finished"):
        logger.info("[EVENT] on_call_ended ignorado — status=%s", sess.get("status"))
        return

    current_sid = sess.get("current_call_sid")
    logger.info("[EVENT] current_call_sid no estado=%s, call_sid recebido=%s", current_sid, call_sid)

    if not current_sid or current_sid != call_sid:
        logger.info("[EVENT] on_call_ended: SID %s não é o atual (%s) — ignorando", call_sid, current_sid)
        return

    _cancel_ring_timer(sess)

    # Se ainda há phones não tentados para este lead, tenta próximo phone ANTES de marcar no_answer
    current_lead_id = sess.get("current_lead_id")
    logger.info("[EVENT] Verificando próximo phone: lead_id=%s, disposition=%s", current_lead_id, disposition)
    if current_lead_id and disposition in ("no_answer", "busy", "voicemail", "failed"):
        lead = Lead.query.filter_by(id=current_lead_id, company_id=company_id).first()
        if lead:
            run_since = None
            try:
                run_since = datetime.fromisoformat(sess["started_at"])
            except Exception:
                pass
            next_phone = _next_phone_for_lead(lead, campaign_id, company_id, since=run_since, mobile_only=sess.get("mobile_only", False))
            logger.info("[EVENT] Verificando próximo phone para lead %s: %s", lead.id, next_phone)
            if next_phone:
                logger.info("[EVENT] Lead %s ainda tem phone %s → tentando próximo número", lead.id, next_phone)
                lead.status = "new"
                db.session.commit()
                sess["status"]           = "running"
                sess["current_call_sid"] = None
                sess["current_lead_id"] = None  # força re-busca do mesmo lead
                dial_next_in_session(campaign_id, company_id, force=True)
                return

    # Se for AMD detectando máquina e não há mais telefones, avança sem pausar para o operador
    if force_advance:
        logger.info("[EVENT] Chamada %s (%s) finalizada sem mais números → Avanço forçado (AMD)", call_sid, disposition)
        sess["status"] = "running"
        sess["current_call_sid"] = None
        sess["current_lead_id"] = None
        
        if current_lead_id:
            try:
                lead = Lead.query.filter_by(id=current_lead_id, company_id=company_id).first()
                # Preserva "retry" (voicemail incerto) e "voicemail" — AMD já classificou.
                # Sobrescrever para "exhausted" descartaria leads que deveriam ser retentados.
                if lead and lead.status not in ("completed", "exhausted", "invalid", "retry", "voicemail"):
                    lead.status = "exhausted"
                    db.session.commit()
            except Exception:
                pass

        _advance(campaign_id, company_id, delay=0)
        return

    # Chamada atendida: pausa para o operador classificar (salvar resultado e avançar via popup)
    if disposition == "answered":
        logger.info("[EVENT] Chamada %s atendida → Pausando para classificação do operador", call_sid)
        sess["status"] = "paused"
        sess["current_call_sid"] = None
        try:
            from app.models.campaign import Campaign
            campaign = Campaign.query.get(campaign_id)
            if campaign:
                campaign.status = "paused"
                db.session.commit()
        except Exception as exc:
            logger.error("[EVENT] Erro ao pausar campanha no DB: %s", exc)
        return

    # Chamada não atendida (no_answer, busy, failed, voicemail sem force_advance) sem mais números:
    # avança automaticamente para o próximo lead sem pausar.
    logger.info("[EVENT] Chamada %s encerrada (%s) sem mais números → avançando para próximo lead", call_sid, disposition)

    # Garante que o lead sai do status "dialing" para não ficar preso.
    # Ring-timer (50s) já faz isso para timeouts, mas quando o Twilio antecipa o no-answer
    # o timer é cancelado aqui e o lead ficaria em "dialing" indefinidamente sem este bloco.
    if current_lead_id and disposition in ("no_answer", "busy", "failed"):
        try:
            _lead = Lead.query.filter_by(id=current_lead_id, company_id=company_id).first()
            if _lead and _lead.status in ("dialing", "ringing"):
                _lead.status = disposition   # "no_answer" | "busy" | "failed"
                db.session.commit()
        except Exception:
            db.session.rollback()

    sess["current_call_sid"] = None
    _advance(campaign_id, company_id, delay=delay if delay else 2)


# ── Advance ───────────────────────────────────────────────────────────────────

def _advance(campaign_id: int, company_id: int, delay: int = 0):
    """Agenda a próxima discagem. Thread-safe via lock em dial_next_in_session."""
    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess or sess.get("status") in ("paused", "stopped", "finished", "in_call"):
        return

    if delay <= 0:
        dial_next_in_session(campaign_id, company_id)
        return

    try:
        app = _get_app()
    except Exception:
        return

    def _run():
        time.sleep(delay)
        with app.app_context():
            s = AUTO_DIALER_SESSIONS.get(campaign_id)
            if s and s.get("status") == "running":
                dial_next_in_session(campaign_id, company_id)

    t = threading.Thread(target=_run, daemon=True, name=f"Advance-{campaign_id}")
    t.start()


def resume_auto_dialer_for_campaign(campaign_id, company_id, delay_override=None):
    """
    Ponto de entrada compatível com chamadores legados (twilio_voice.py).
    Reseta status para 'running' e agenda próxima discagem.
    """
    campaign_id = int(campaign_id)
    company_id  = int(company_id)

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess:
        return

    if sess.get("status") in ("paused", "stopped", "finished", "in_call"):
        logger.info("[RESUME] Ignorado — status=%s", sess.get("status"))
        return

    delay = delay_override if delay_override is not None else 0
    sess["status"] = "running"
    _advance(campaign_id, company_id, delay=delay)


# ── Core dial ─────────────────────────────────────────────────────────────────

def dial_next_in_session(campaign_id: int, company_id: int, force: bool = False, skip_current_id: int = None) -> tuple:
    """
    Dispara a próxima ligação. Thread-safe via Lock não-bloqueante por sessão.
    Se outra thread já está discando, retorna imediatamente sem duplicar.
    """
    campaign_id = int(campaign_id)
    company_id  = int(company_id)

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess:
        return False, "sessão não existe"

    lock: threading.Lock = sess["_lock"]
    if not lock.acquire(blocking=False):
        logger.info("[DIALER] Lock ocupado para campaign=%s — descartando chamada duplicada", campaign_id)
        return False, "discagem já em progresso"

    try:
        return _dial_locked(campaign_id, company_id, sess, force=force, skip_current_id=skip_current_id)
    finally:
        lock.release()


def _dial_locked(campaign_id, company_id, sess, force=False, skip_current_id=None):
    """Lógica principal de discagem — executada com lock já adquirido."""
    status = sess.get("status")
    if not force and status != "running":
        logger.info("[DIALER] dial_next ignorado: status=%s", status)
        return False, f"sessão não ativa (status: {status})"

    public_base = _get_public_base_url()
    if not public_base:
        return False, "PUBLIC_BASE_URL não configurado"

    run_since = None
    try:
        run_since = datetime.fromisoformat(sess["started_at"])
    except Exception:
        pass

    mobile_only = sess.get("mobile_only", False)
    skipped     = set()
    if skip_current_id:
        skipped.add(skip_current_id)

    # ── Priority lead (AMD recovery) tem máxima prioridade ──────────────
    lead = None
    priority_lead_id = sess.pop("_priority_lead_id", None)
    if priority_lead_id:
        priority_lead = Lead.query.filter_by(id=priority_lead_id, company_id=company_id).first()
        if priority_lead and priority_lead.campaign_id == campaign_id:
            phone_check = _next_phone_for_lead(priority_lead, campaign_id, company_id, ignore_history=True)
            if phone_check:
                lead = priority_lead
                logger.info("[DIALER] Discando lead prioritário (AMD recovery): lead_id=%s", priority_lead_id)

    # ── Callback queue tem prioridade ─────────────────────────────────────
    cb = None
    if not lead:
        cb = (
            CallbackQueue.query
            .filter(
                CallbackQueue.campaign_id == campaign_id,
                CallbackQueue.status      == CallbackStatus.PENDING.value,
                CallbackQueue.scheduled_for <= datetime.utcnow(),
            )
            .order_by(CallbackQueue.priority.desc(), CallbackQueue.scheduled_for.asc())
            .first()
        )
        if cb:
            lead = Lead.query.filter_by(id=cb.lead_id, company_id=company_id).first()
            if lead:
                cb.status   = CallbackStatus.DIALING.value
                cb.attempts += 1
                db.session.commit()

    if not lead:
        lead = _next_lead_query(campaign_id, company_id, skipped)

    # ── Itera até achar lead + telefone discáveis ─────────────────────────
    while True:
        if lead is None:
            sess["status"]           = "finished"
            sess["current_lead_id"]  = None
            sess["current_call_sid"] = None
            obj = Campaign.query.filter_by(id=campaign_id, company_id=company_id).first()
            if obj:
                obj.status = "finished"
                db.session.commit()
            logger.info("[DIALER] Campaign %s finalizada — sem mais leads", campaign_id)
            return True, "campanha finalizada"

        if not lead.get_all_phones():
            lead.status = "invalid"
            db.session.commit()
            logger.warning("[DIALER] Lead %s sem telefone — pulando", lead.id)
            skipped.add(lead.id)
            lead = _next_lead_query(campaign_id, company_id, skipped)
            continue

        phone = _next_phone_for_lead(lead, campaign_id, company_id, since=run_since, mobile_only=mobile_only, ignore_history=(cb is not None))
        if phone:
            break

        # Todos os números deste lead foram tentados
        lead.status = "exhausted"
        db.session.commit()
        logger.info("[DIALER] Lead %s — todos os números tentados → exhausted", lead.id)
        skipped.add(lead.id)
        lead = _next_lead_query(campaign_id, company_id, skipped)

    # ── Agente ───────────────────────────────────────────────────────────
    agent = (
        Agent.query
        .filter(Agent.company_id == company_id, Agent.status.in_(["available", "online", "ready"]))
        .order_by(Agent.id.asc())
        .first()
    ) or Agent.query.filter(Agent.company_id == company_id).order_by(Agent.id.asc()).first()

    if not agent:
        sess["status"] = "paused"
        return False, "nenhum operador disponível — sessão pausada"

    # ── Twilio ────────────────────────────────────────────────────────────
    company = Company.query.get(company_id)
    try:
        svc = TwilioService.from_company(company, current_user_email=sess.get("user_email"))
    except ValueError as e:
        return False, str(e)

    conf_name  = f"agent_bridge_{agent.id}"
    status_url = f"{public_base}/api/twilio/status"
    conf_url   = f"{public_base}/api/twilio/conference-events"

    last_attempt = (
        db.session.query(db.func.max(Call.attempt))
        .filter(Call.lead_id == lead.id, Call.company_id == company_id)
        .scalar()
    ) or 0

    db_call = Call(
        company_id       = company_id,
        campaign_id      = campaign_id,
        lead_id          = lead.id,
        agent_id         = agent.id,
        phone_dialed     = phone,
        direction        = "outbound",
        status           = "dialing",
        duration_seconds = 0,
        attempt          = last_attempt + 1,
    )
    db.session.add(db_call)
    lead.status = "dialing"
    db.session.flush()

    register_pending_conference(
        conference_name = conf_name,
        agent_id        = agent.id,
        lead_id         = lead.id,
        phone_number    = phone,
        lead_name       = getattr(lead, "name", None),
        company_name    = getattr(lead, "company_name", None),
        campaign_id     = campaign_id,
        company_id      = company_id,
        db_call_id      = db_call.id,
        lead_call_sid   = None,
        amd_enabled     = True,
        user_email      = sess.get("user_email"),
    )

    # FASE 1 FIX: AMD NÃO funciona com <Dial><Conference> (documentação Twilio explícita).
    # Usamos url= apontando para /amd-hold que faz um Pause silencioso enquanto o AMD
    # analisa a chamada. Ao confirmar humano, o /amd-callback redireciona via REST API
    # para /lead-entry que coloca o lead na conferência correta.
    amd_hold_url    = f"{public_base}/api/twilio/amd-hold?c={conf_name}&lead_id={lead.id}"
    amd_callback_url = f"{public_base}/api/twilio/amd-callback?c={conf_name}"

    try:
        result = svc.client.calls.create(
            to                     = phone,
            from_                  = svc.twilio_number,
            url                    = amd_hold_url,   # <-- CRÍTICO: url= em vez de twiml=
            status_callback        = f"{status_url}?c={conf_name}",
            status_callback_event  = ["initiated", "ringing", "answered", "completed"],
            status_callback_method = "POST",
            machine_detection      = "Enable",
            async_amd              = "true",
            async_amd_status_callback         = amd_callback_url,
            async_amd_status_callback_method  = "POST",
            # Parâmetros AMD para operadoras brasileiras (Vivo/Claro/TIM/Oi).
            # speech_end_threshold=2500: caixas postais BR têm pausas de ~1,5-2,5s no
            #   meio da saudação — valor menor fazia o AMD decidir antes de ver a pausa
            #   e classificava erroneamente como humano.
            # O padrão "alô+pausa+alô" que causava FP em humanos é resolvido pelo
            #   <Say> no /amd-hold: o lead ouve "Um momento" e não repete o alô,
            #   então o AMD analisa um único "alô" + 2,5s de silêncio = humano.
            machine_detection_timeout              = 15,
            machine_detection_speech_threshold     = 2400,
            machine_detection_speech_end_threshold = 2500,
            machine_detection_silence_timeout      = 3000,
            timeout                = 55,
        )
    except InsufficientCreditError as credit_err:
        # Saldo zerado — pausa campanha imediatamente, não tenta próximo lead
        db.session.rollback()
        if conf_name.startswith("agent_bridge_"):
            from app.services.call_bridge import ACTIVE_CONFERENCES_BY_NAME
            item = ACTIVE_CONFERENCES_BY_NAME.get(conf_name)
            if item:
                item["lead_id"] = None
                item["db_call_id"] = None
                item["lead_call_sid"] = None
                item["status"] = "idle"
                ACTIVE_CONFERENCES_BY_NAME.pop(conf_name, None)
        else:
            clear_pending_conference(conf_name)
        try:
            lead.status = "new"
            db.session.commit()
        except Exception:
            db.session.rollback()
        sess["status"] = "paused"
        sess["pause_reason"] = "insufficient_credit"
        logger.warning("[DIALER] Campanha %s pausada — saldo insuficiente: %s", campaign_id, credit_err)
        return False, str(credit_err)
    except Exception as exc:
        db.session.rollback()
        if conf_name.startswith("agent_bridge_"):
            from app.services.call_bridge import ACTIVE_CONFERENCES_BY_NAME
            item = ACTIVE_CONFERENCES_BY_NAME.get(conf_name)
            if item:
                item["lead_id"] = None
                item["db_call_id"] = None
                item["lead_call_sid"] = None
                item["status"] = "idle"
                ACTIVE_CONFERENCES_BY_NAME.pop(conf_name, None)
        else:
            clear_pending_conference(conf_name)
        logger.error("[DIALER] Erro Twilio lead %s (%s): %s", lead.id, phone, exc, exc_info=True)
        # Registra telefone como falho para não tentar de novo nesta sessão
        try:
            fail = Call(
                company_id       = company_id,
                campaign_id      = campaign_id,
                lead_id          = lead.id,
                agent_id         = agent.id,
                phone_dialed     = phone,
                direction        = "outbound",
                status           = "failed",
                duration_seconds = 0,
                attempt          = last_attempt + 1,
            )
            db.session.add(fail)
            lead.status = "new"
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Pausa a campanha em vez de avançar recursivamente quando há erro de configuração Twilio
        # (ex: número não verificado, saldo zerado, credenciais inválidas)
        exc_str = str(exc).lower()
        is_config_error = any(k in exc_str for k in [
            "not yet verified", "not verified", "21210",
            "authentication", "auth", "credentials", "21608",
            "permission", "account suspended", "account is not active",
        ])
        if is_config_error:
            sess["status"] = "paused"
            sess["pause_reason"] = "twilio_config_error"
            sess["pause_detail"] = str(exc)[:300]
            logger.warning("[DIALER] Campanha %s pausada por erro de configuração Twilio: %s", campaign_id, exc)
            return False, f"Erro de configuração Twilio: {exc}"
        # Tenta próximo telefone imediatamente (mesmo lead, telefone registrado como falho)
        return _dial_locked(campaign_id, company_id, sess, force=True)

    # ── Sucesso: atualiza estado ──────────────────────────────────────────
    db_call.call_sid = result.sid
    db_call.status   = "ringing"
    lead.status      = "dialing"
    update_pending_lead_call_sid(conf_name, result.sid)
    db.session.commit()

    # Marca status como ringing_lead para o poller saber que está discando
    bridge_item = ACTIVE_CONFERENCES_BY_AGENT.get(agent.id)
    if bridge_item:
        bridge_item["status"] = "ringing_lead"
        # lead_answered_at NÃO é setado aqui — só quando o lead realmente atende
        # (conference_events → participant-join). Isso impede popup prematuro.
        logger.info("[DIALER] Discando lead=%s SID=%s", lead.id, result.sid)

    # Cancela timer anterior e inicia novo (50s)
    _cancel_ring_timer(sess)

    all_phones = lead.get_all_phones()
    
    # Normaliza a lista para encontrar o índice correto, já que 'phone' já está normalizado
    norm_all_phones = []
    for p in all_phones:
        raw_p = str(p).strip()
        if raw_p.endswith(".0"):
            raw_p = raw_p[:-2]
        norm_all_phones.append(normalize_phone_br(raw_p))
        
    phone_idx = (norm_all_phones.index(phone) + 1) if phone in norm_all_phones else 1

    sess["status"]               = "ringing"
    sess["current_lead_id"]      = lead.id
    sess["current_lead_name"]    = lead.name
    sess["current_lead_phone"]   = phone
    sess["current_lead_company"] = getattr(lead, "company_name", None) or ""
    sess["current_call_sid"]     = result.sid
    sess["leads_done"]           = sess.get("leads_done", 0) + 1
    sess["current_phone_index"]  = phone_idx
    sess["current_phone_total"]  = len(all_phones)

    _start_ring_timer(campaign_id, company_id, result.sid, sess)

    logger.info("=" * 60)
    logger.info("[DISCANDO] Lead=%s | %s | %s | Campaign=%s | SID=%s",
                lead.id, lead.name, phone, campaign_id, result.sid)
    logger.info("=" * 60)

    return True, conf_name


# ── Endpoints HTTP ────────────────────────────────────────────────────────────

@auto_dialer_bp.route("/start", methods=["POST"])
@require_auth
def start_auto():
    body = request.get_json(silent=True) or {}
    try:
        campaign_id = int(body["campaign_id"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "campaign_id inválido"}), 400

    interval_sec = int(body.get("interval_seconds", 3))
    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    dialable_statuses = [
        "new", "novo", "tentativa", "tentando", "retry", "callback",
        "retornar", "qualified", "no_answer", "busy", "failed", "voicemail", "invalid_number"
    ]

    # Reinício de campanha: reseta leads e histórico de chamadas para poder re-discar
    is_restart = campaign.status in ("finished", "paused", "stopped")
    if not is_restart:
        dialable_count = Lead.query.filter(
            Lead.campaign_id == campaign_id,
            Lead.company_id  == g.company_id,
            Lead.status.in_(dialable_statuses),
        ).count()
        is_restart = (dialable_count == 0)

    if is_restart:
        reset_statuses = ["completed", "exhausted", "answered", "contacted", "converted", "dialing", "invalid", "failed", "no_answer"]
        Lead.query.filter(
            Lead.campaign_id == campaign_id,
            Lead.company_id  == g.company_id,
            Lead.status.in_(reset_statuses),
        ).update({"status": "new"}, synchronize_session=False)
        # Marca chamadas antigas como "reset" para _phones_tried ignorá-las
        Call.query.filter(
            Call.campaign_id == campaign_id,
            Call.company_id  == g.company_id,
        ).update({"status": "reset"}, synchronize_session=False)
        db.session.flush()
        logger.info("[START] Campanha %s reiniciada — leads e histórico de chamadas resetados", campaign_id)

    leads_total = Lead.query.filter(
        Lead.campaign_id == campaign_id,
        Lead.company_id  == g.company_id,
        Lead.status.in_(dialable_statuses),
    ).count()

    AUTO_DIALER_SESSIONS[campaign_id] = _new_session(
        campaign_id, g.company_id, campaign.name,
        interval_sec, leads_total, bool(campaign.mobile_only),
        user_email=getattr(g, 'user_email', None)
    )
    campaign.status = "running"
    db.session.commit()

    try:
        ok, msg = dial_next_in_session(campaign_id, g.company_id)
    except Exception as e:
        logger.error(f"[START] Erro interno: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": f"Erro interno ao iniciar: {str(e)}"}), 500

    return jsonify({
        "message":    "Discador automático iniciado",
        "ok":         ok,
        "first_dial": msg,
        "session":    _session_for_json(AUTO_DIALER_SESSIONS[campaign_id]),
    }), 200


@auto_dialer_bp.route("/stop", methods=["POST"])
@require_auth
def stop_auto():
    body        = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if sess:
        _cancel_ring_timer(sess)
        sess["status"] = "stopped"

    # Encerra chamadas ativas no Twilio para não deixar leads tocando
    try:
        company = Company.query.get(g.company_id)
        if company:
            svc = TwilioService.from_company(company, current_user_email=sess.get("user_email") if sess else getattr(g, 'user_email', None))
            active = Call.query.filter(
                Call.campaign_id == campaign_id,
                Call.status.in_(["ringing", "dialing", "waiting_agent", "in-progress", "answered", "agent_joined"]),
            ).all()
            for c in active:
                if c.call_sid:
                    try:
                        svc.client.calls(c.call_sid).update(status="completed")
                    except Exception:
                        pass
                c.status = "no_answer"
                c.ended_at = datetime.utcnow()
                _clear_bridge_for_sid(c.call_sid)
    except Exception as e:
        logger.warning(f"[STOP] Erro ao cancelar chamadas: {e}")

    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    if campaign:
        campaign.status = "paused"
        db.session.commit()

    return jsonify({"message": "Discador parado"}), 200


@auto_dialer_bp.route("/pause", methods=["POST"])
@require_auth
def pause_auto():
    body        = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if sess:
        sess["status"] = "paused"
        _cancel_ring_timer(sess)

    # Encerra chamadas ativas no Twilio para não deixar leads tocando
    try:
        company = Company.query.get(g.company_id)
        if company:
            svc = TwilioService.from_company(company, current_user_email=sess.get("user_email") if sess else getattr(g, 'user_email', None))
            active = Call.query.filter(
                Call.campaign_id == campaign_id,
                Call.status.in_(["ringing", "dialing", "waiting_agent", "in-progress", "answered", "agent_joined"]),
            ).all()
            for c in active:
                if c.call_sid:
                    try:
                        svc.client.calls(c.call_sid).update(status="completed")
                    except Exception:
                        pass
                c.status = "no_answer"
                c.ended_at = datetime.utcnow()
                _clear_bridge_for_sid(c.call_sid)
    except Exception as e:
        logger.warning(f"[PAUSE] Erro ao cancelar chamadas: {e}")

    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    if campaign:
        campaign.status = "paused"
        db.session.commit()

    return jsonify({"message": "Discador pausado"}), 200


@auto_dialer_bp.route("/resume", methods=["POST"])
@require_auth
def resume_auto():
    body        = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess:
        leads_remaining = Lead.query.filter(
            Lead.campaign_id == campaign_id,
            Lead.company_id  == g.company_id,
            Lead.status.in_(["new", "novo"]),
        ).count()
        AUTO_DIALER_SESSIONS[campaign_id] = _new_session(
            campaign_id, g.company_id, campaign.name,
            3, leads_remaining, bool(campaign.mobile_only),
            user_email=getattr(g, 'user_email', None)
        )
        sess = AUTO_DIALER_SESSIONS[campaign_id]
    else:
        if sess.get("status") == "finished":
            leads_remaining = Lead.query.filter(
                Lead.campaign_id == campaign_id,
                Lead.company_id  == g.company_id,
                Lead.status.in_(["new", "novo"]),
            ).count()
            sess["leads_total"] = leads_remaining
            sess["leads_done"]  = 0
            sess["started_at"]  = datetime.utcnow().isoformat()
        sess["status"] = "running"

    campaign.status = "running"
    db.session.commit()

    ok, msg = dial_next_in_session(campaign_id, g.company_id)
    return jsonify({
        "message": "Discador retomado",
        "ok":      ok,
        "msg":     msg,
        "session": _session_for_json(AUTO_DIALER_SESSIONS[campaign_id]),
    }), 200


@auto_dialer_bp.route("/next", methods=["POST"])
@require_auth
def next_lead():
    """Pula o lead atual e vai para o próximo imediatamente."""
    body        = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess or sess.get("company_id") != g.company_id:
        return jsonify({"error": "Sessão não encontrada"}), 404

    _cancel_ring_timer(sess)

    current_lead_id = sess.get("current_lead_id")
    current_sid     = sess.get("current_call_sid")

    # Encerra chamadas ativas no Twilio
    company = Company.query.get(g.company_id)
    try:
        svc = TwilioService.from_company(company, current_user_email=sess.get("user_email") if sess else getattr(g, 'user_email', None))
        active = Call.query.filter(
            Call.campaign_id == campaign_id,
            Call.status.in_(["ringing", "dialing", "waiting_agent", "in-progress", "answered", "agent_joined"]),
        ).all()
        if not isinstance(sess.get("_cancelled_sids"), set):
            sess["_cancelled_sids"] = set()
        for c in active:
            if c.call_sid:
                sess["_cancelled_sids"].add(c.call_sid)
                try:
                    svc.client.calls(c.call_sid).update(status="completed")
                except Exception:
                    pass
            c.status   = "no_answer"
            c.ended_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        logger.warning("[NEXT] Erro ao cancelar chamadas: %s", e)

    # Marca lead atual como exhausted para que não seja discado novamente
    if current_lead_id:
        lead = Lead.query.filter_by(id=current_lead_id, company_id=g.company_id).first()
        if lead and lead.status not in ("completed", "exhausted", "invalid"):
            lead.status = "exhausted"
            db.session.commit()

    if current_sid:
        _clear_bridge_for_sid(current_sid)

    sess["status"]           = "running"
    sess["current_lead_id"]  = None
    sess["current_call_sid"] = None

    ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True, skip_current_id=current_lead_id)
    return jsonify({
        "message": "Próximo lead",
        "ok":      ok,
        "msg":     msg,
        "session": _session_for_json(AUTO_DIALER_SESSIONS.get(campaign_id) or {}),
    }), 200


@auto_dialer_bp.route("/skip_phone", methods=["POST"])
@require_auth
def skip_phone():
    """Pula para o próximo número do mesmo lead (mantém lead atual)."""
    body        = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess or sess.get("company_id") != g.company_id:
        return jsonify({"error": "Sessão não encontrada"}), 404

    current_lead_id = sess.get("current_lead_id")
    if not current_lead_id:
        return jsonify({"error": "Nenhum lead ativo"}), 400

    lead = Lead.query.filter_by(id=current_lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    # Cancela chamada atual
    _cancel_ring_timer(sess)
    current_sid = sess.get("current_call_sid")

    company = Company.query.get(g.company_id)
    try:
        svc = TwilioService.from_company(company, current_user_email=sess.get("user_email") if sess else getattr(g, 'user_email', None))
        if not isinstance(sess.get("_cancelled_sids"), set):
            sess["_cancelled_sids"] = set()
        for item in list(ACTIVE_CONFERENCES_BY_AGENT.values()):
            if item.get("campaign_id") == int(campaign_id):
                sid = item.get("lead_call_sid")
                if sid:
                    sess["_cancelled_sids"].add(sid)
                    try:
                        svc.client.calls(sid).update(status="completed")
                    except Exception:
                        pass
                # Limpa apenas dados do lead — preserva agent_leg_call_sid da ponte persistente
                conf_name = item.get("conference_name", "")
                if conf_name.startswith("agent_bridge_"):
                    item["lead_id"]          = None
                    item["db_call_id"]       = None
                    item["lead_call_sid"]    = None
                    item["audio_bridged"]    = False
                    item["lead_answered_at"] = None
                    item["status"]           = "idle"
                    # Remove do index por nome para register_pending_conference não confundir
                    from app.services.call_bridge import ACTIVE_CONFERENCES_BY_NAME
                    ACTIVE_CONFERENCES_BY_NAME.pop(conf_name, None)
                else:
                    clear_pending_conference(conf_name)
    except Exception as e:
        logger.warning("[SKIP-PHONE] Erro ao cancelar chamada: %s", e)

    # Marca chamada atual como no_answer (para _phones_tried excluí-la)
    current_call = Call.query.filter(
        Call.lead_id     == current_lead_id,
        Call.campaign_id == campaign_id,
        Call.status.in_(["ringing", "dialing", "waiting_agent"]),
    ).order_by(Call.created_at.desc()).first()
    if current_call:
        current_call.status   = "no_answer"
        current_call.ended_at = datetime.utcnow()
        db.session.commit()

    if current_sid:
        _clear_bridge_for_sid(current_sid)

    # Verifica se há próximo número
    run_since = None
    try:
        run_since = datetime.fromisoformat(sess["started_at"])
    except Exception:
        pass

    next_ph = _next_phone_for_lead(
        lead, campaign_id, g.company_id,
        since=run_since, mobile_only=sess.get("mobile_only", False),
    )
    if not next_ph:
        # Sem mais números → avança para próximo lead
        lead.status = "no_answer"
        db.session.commit()
        sess["status"]           = "running"
        sess["current_lead_id"]  = None
        sess["current_call_sid"] = None
        ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True)
        return jsonify({"ok": ok, "msg": msg or "Todos os números tentados — próximo lead", "has_next_phone": False}), 200

    # Reseta lead para "new" e reusa dial_next_in_session (ele vai pegar o próximo número)
    lead.status = "new"
    db.session.commit()

    sess["status"]           = "running"
    sess["current_lead_id"]  = None   # limpa para dial_next encontrar o lead novamente
    sess["current_call_sid"] = None

    ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True)
    return jsonify({
        "ok":             ok,
        "msg":            msg,
        "lead_id":        lead.id,
        "lead_name":      sess.get("current_lead_name") or lead.name,
        "phone":          sess.get("current_lead_phone") or "",
        "has_next_phone": True,
        "session":        _session_for_json(sess),
    }), 200


@auto_dialer_bp.route("/classified", methods=["POST"])
@require_auth
def lead_classified():
    """ called by frontend after operator classifies a lead.
    Advances to next number in the same lead, or next lead.
    """
    body = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = AUTO_DIALER_SESSIONS.get(campaign_id)
    if not sess or sess.get("company_id") != g.company_id:
        return jsonify({"error": "Sessão não encontrada"}), 404

    current_lead_id = sess.get("current_lead_id")
    current_call_sid = sess.get("current_call_sid")

    # Clear bridge state to allow next call
    if current_call_sid:
        _clear_bridge_for_sid(current_call_sid)

    # Check if there are more phones to try for this lead
    if current_lead_id:
        lead = Lead.query.filter_by(id=current_lead_id, company_id=g.company_id).first()
        if lead:
            run_since = None
            try:
                run_since = datetime.fromisoformat(sess["started_at"])
            except Exception:
                pass

            next_phone = _next_phone_for_lead(
                lead, campaign_id, g.company_id,
                since=run_since, mobile_only=sess.get("mobile_only", False),
            )

            if next_phone:
                logger.info("[CLASSIFIED] Lead %s tem próximo phone %s → discando", lead.id, next_phone)
                lead.status = "new"
                db.session.commit()
                sess["status"] = "running"
                sess["current_call_sid"] = None
                sess["current_lead_id"] = None
                ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True)
                return jsonify({
                    "ok": ok,
                    "msg": "Próximo número do mesmo lead",
                    "next_phone": next_phone,
                }), 200

    # No more phones → go to next lead
    logger.info("[CLASSIFIED] Indo para próximo lead")
    lead = Lead.query.filter_by(id=current_lead_id, company_id=g.company_id).first()
    if lead:
        lead.status = "new"
        db.session.commit()

    sess["status"] = "running"
    sess["current_lead_id"] = None
    sess["current_call_sid"] = None

    ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True)
    return jsonify({
        "ok": ok,
        "msg": msg or "Próximo lead",
    }), 200


@auto_dialer_bp.route("/status/<int:campaign_id>", methods=["GET"])
@require_auth
def auto_status(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    sess     = AUTO_DIALER_SESSIONS.get(campaign_id)
    if sess and sess.get("company_id") != g.company_id:
        sess = None

    leads_total     = Lead.query.filter(
        Lead.campaign_id == campaign_id, Lead.company_id == g.company_id,
    ).count()
    leads_remaining = Lead.query.filter(
        Lead.campaign_id == campaign_id, Lead.company_id == g.company_id,
        Lead.status.in_(["new", "novo"]),
    ).count()
    leads_done  = leads_total - leads_remaining
    progress    = round(leads_done / leads_total * 100, 2) if leads_total else 0

    active_call = (
        Call.query
        .filter(
            Call.campaign_id == campaign_id,
            Call.company_id  == g.company_id,
            Call.status.in_([
                "ringing", "dialing", "waiting_agent", "answered",
                "in-progress", "answered_waiting_agent", "agent_joining", "agent_joined",
            ]),
        )
        .order_by(Call.created_at.desc())
        .first()
    )
    active_call_data = {
        "id": active_call.id, "call_sid": active_call.call_sid,
        "status": active_call.status, "phone_dialed": active_call.phone_dialed,
        "lead_id": active_call.lead_id,
    } if active_call else None

    raw_status = (sess.get("status") if sess else (campaign.status if campaign else "stopped"))
    return jsonify({
        "status":               raw_status,
        "status_display":       _STATUS_DISPLAY.get(raw_status, raw_status),
        "campaign_id":          campaign_id,
        "campaign_name":        (sess or {}).get("campaign_name") or (campaign.name if campaign else None),
        "current_lead_id":      (sess or {}).get("current_lead_id"),
        "current_lead_name":    (sess or {}).get("current_lead_name"),
        "current_lead_phone":   (sess or {}).get("current_lead_phone"),
        "current_lead_company": (sess or {}).get("current_lead_company"),
        "current_phone_index":  (sess or {}).get("current_phone_index"),
        "current_phone_total":  (sess or {}).get("current_phone_total"),
        "leads_total":          leads_total,
        "leads_done":           leads_done,
        "leads_remaining":      leads_remaining,
        "progress_percent":     progress,
        "active_call":          active_call_data,
        "started_at":           (sess or {}).get("started_at"),
        "pause_reason":         (sess or {}).get("pause_reason"),
        "pause_detail":         (sess or {}).get("pause_detail"),
    }), 200
