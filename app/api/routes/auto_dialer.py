"""
Discador Automático — VoxFlow

Estado de sessão armazenado no Redis (com fallback in-memory).
Objetos não-serializáveis (Lock, Timer, sets) ficam localmente em _LOCAL_STATE.

Estados:
  running  → entre chamadas, buscando próximo lead
  ringing  → chamada criada, aguardando atender
  in_call  → lead atendeu, popup aberto, operador ativo
  paused   → pausado manualmente
  stopped  → parado manualmente
  finished → todos os leads percorridos
"""
import logging
import os
import threading
import time
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.auth import require_auth, rate_limit
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
    ACTIVE_CONFERENCES_BY_NAME,
    clear_pending_conference,
    get_conference_by_agent,
    get_conference_by_name,
    register_pending_conference,
    update_pending_lead_call_sid,
)
from app.services.twilio_service import TwilioService, normalize_phone_br, InsufficientCreditError
from app.services import redis_service

logger = logging.getLogger(__name__)

auto_dialer_bp = Blueprint("auto_dialer", __name__, url_prefix="/api/dialer/auto")

_SESSION_PREFIX = "voxflow:dialer:session:"
_SESSION_TTL    = 86400  # 24h — sessão expira se ficar idle por 1 dia

# Estado local não-serializável (por processo)
_LOCAL_STATE: dict = {}
_LOCAL_STATE_LOCK = threading.Lock()

_STATUS_DISPLAY = {
    "running":  "▶ Discando...",
    "ringing":  "📞 Chamando...",
    "in_call":  "📞 Em conversa",
    "paused":   "⏸ Pausado",
    "stopped":  "⏹ Parado",
    "finished": "✅ Finalizado",
}


# ── Session store helpers ─────────────────────────────────────────────────────

def _session_key(campaign_id: int) -> str:
    return f"{_SESSION_PREFIX}{campaign_id}"


def _local_state(campaign_id: int) -> dict:
    """Retorna (criando se necessário) o estado local da sessão."""
    cid = int(campaign_id)
    with _LOCAL_STATE_LOCK:
        if cid not in _LOCAL_STATE:
            _LOCAL_STATE[cid] = {
                "_lock":           threading.Lock(),
                "_ring_timer":     None,
                "_cancelled_sids": set(),
                "_amd_raced_sids": set(),
            }
        return _LOCAL_STATE[cid]


def _get_session(campaign_id: int) -> dict:
    """Carrega sessão do Redis; merge com estado local."""
    cid = int(campaign_id)
    data = redis_service.get(_session_key(cid))
    if not data or not isinstance(data, dict):
        return None
    local = _local_state(cid)
    # Expõe estado local via referências diretas (sem serializar)
    data["_lock"]           = local["_lock"]
    data["_ring_timer"]     = local["_ring_timer"]
    data["_cancelled_sids"] = local["_cancelled_sids"]
    data["_amd_raced_sids"] = local["_amd_raced_sids"]
    return data


def _save_session(campaign_id: int, sess: dict):
    """Persiste parte serializável da sessão no Redis e emite evento WebSocket."""
    cid = int(campaign_id)
    skip = {"_lock", "_ring_timer", "_cancelled_sids", "_amd_raced_sids"}
    serializable = {k: v for k, v in sess.items() if k not in skip}
    redis_service.set(_session_key(cid), serializable, ex=_SESSION_TTL)

    # Emite evento real-time para substituir polling
    try:
        from app.services.socket_service import emit_dialer_status
        company_id = serializable.get("company_id")
        if company_id:
            emit_dialer_status(int(company_id), cid, serializable)
    except Exception:
        pass  # WebSocket é best-effort — nunca bloqueia a lógica principal


def _delete_session(campaign_id: int):
    redis_service.delete(_session_key(int(campaign_id)))
    with _LOCAL_STATE_LOCK:
        _LOCAL_STATE.pop(int(campaign_id), None)


def _new_session(campaign_id, company_id, campaign_name, interval_sec, leads_total,
                 mobile_only=False, user_email=None, dial_mode='auto', predictive_ratio=1.5):
    data = {
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
        "current_call_sid":     None,
        # Preditivo
        "dial_mode":            dial_mode,
        "predictive_ratio":     max(1.0, min(3.0, float(predictive_ratio or 1.5))),
        "concurrent_sids":      [],    # SIDs de chamadas preditivas em voo
    }
    # Garante estado local limpo
    with _LOCAL_STATE_LOCK:
        _LOCAL_STATE[int(campaign_id)] = {
            "_lock":           threading.Lock(),
            "_ring_timer":     None,
            "_cancelled_sids": set(),
            "_amd_raced_sids": set(),
        }
    _save_session(campaign_id, data)
    return _get_session(campaign_id)


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


def _phones_tried(lead_id, campaign_id, company_id) -> set:
    q = Call.query.filter(
        Call.lead_id     == lead_id,
        Call.campaign_id == campaign_id,
        Call.company_id  == company_id,
        Call.phone_dialed.isnot(None),
        Call.status != "reset",
    )
    return {normalize_phone_br(c.phone_dialed) for c in q.all() if c.phone_dialed}


def _next_phone_for_lead(lead, campaign_id, company_id, _since=None, mobile_only=False, ignore_history=False):
    if ignore_history:
        tried = set()
    else:
        tried = _phones_tried(lead.id, campaign_id, company_id)
    logger.info("[PHONE] _next_phone_for_lead: lead=%s, tried=%s", lead.id, tried)
    for raw in lead.get_all_phones():
        raw = str(raw).strip()
        if raw.endswith(".0"):
            raw = raw[:-2]
        norm = normalize_phone_br(raw)
        if mobile_only and not is_mobile_br(norm):
            continue
        if norm not in tried:
            logger.info("[PHONE] Lead=%s → próximo: %s", lead.id, norm)
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

def _cancel_twilio_call(company_id, call_sid, user_email=None):
    try:
        company = Company.query.get(company_id)
        if company:
            svc = TwilioService.from_company(company, current_user_email=user_email)
            svc.client.calls(call_sid).update(status="completed")
            logger.info("[DIALER] Chamada %s encerrada no Twilio", call_sid)
    except Exception as e:
        logger.warning("[DIALER] Erro ao cancelar %s: %s", call_sid, e)


def _clear_bridge_for_sid(call_sid: str):
    """Limpa estado de conferência para o SID informado."""
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
                from app.services.call_bridge import update_conference
                update_conference(conf, **{k: item[k] for k in item if not k.startswith("_")})
            else:
                clear_pending_conference(conf)
            logger.info("[BRIDGE] Estado limpo para SID %s (conf=%s)", call_sid, conf)
            return


# ── Ring timer ────────────────────────────────────────────────────────────────

_SID_ANSWERED_PREFIX = "voxflow:answered:"
_SID_TIMEOUT_PREFIX  = "voxflow:ring_timeout:"


def _mark_sid_answered(call_sid: str):
    """Marca SID como atendido no Redis para que o ring timer não o cancele."""
    redis_service.set(f"{_SID_ANSWERED_PREFIX}{call_sid}", "1", ex=120)


def _is_sid_answered(call_sid: str) -> bool:
    return bool(redis_service.get(f"{_SID_ANSWERED_PREFIX}{call_sid}"))


def _cancel_ring_timer(sess: dict):
    local = _local_state(sess["campaign_id"])
    t = local.get("_ring_timer")
    if isinstance(t, threading.Timer) and t.is_alive():
        t.cancel()
    local["_ring_timer"] = None


def _start_ring_timer(campaign_id: int, company_id: int, call_sid: str, sess: dict, timeout_seconds: int = 50):
    app = _get_app()

    def _fire():
        logger.info("[TIMEOUT] %ds expirou para %s — encerrando chamada", timeout_seconds, call_sid)
        with app.app_context():
            # Mutex Redis: garante que apenas um processo execute o timeout por SID
            lock_key = f"{_SID_TIMEOUT_PREFIX}{call_sid}"
            acquired = redis_service.setnx(lock_key, "1", ex=30)
            if not acquired:
                logger.info("[TIMEOUT] SID %s já está sendo processado por outro worker — ignorando", call_sid)
                return

            # Se o lead já atendeu (sinalizado por on_lead_answered ou AMD), aborta
            if _is_sid_answered(call_sid):
                logger.info("[TIMEOUT] SID %s já foi atendido — timeout cancelado", call_sid)
                return

            s = _get_session(campaign_id)
            if not s:
                return

            # Adquire o lock local para evitar race dentro do mesmo processo
            local = _local_state(campaign_id)
            lock = local.get("_lock")
            acquired_local = lock.acquire(timeout=5) if lock else False
            try:
                # Re-verifica estado após obter lock
                s = _get_session(campaign_id)
                if not s:
                    return
                if s.get("current_call_sid") != call_sid:
                    logger.info("[TIMEOUT] SID %s não é mais o atual — ignorando", call_sid)
                    return
                if s.get("status") not in ("ringing", "running"):
                    logger.info("[TIMEOUT] Status=%s — timeout ignorado", s.get("status"))
                    return
                if _is_sid_answered(call_sid):
                    logger.info("[TIMEOUT] SID %s atendido entre checks — cancelando timeout", call_sid)
                    return

                local["_ring_timer"] = None
                _cancel_twilio_call(company_id, call_sid, user_email=s.get("user_email"))

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
            finally:
                if acquired_local and lock:
                    lock.release()

    local = _local_state(campaign_id)
    # Cancela timer anterior
    old = local.get("_ring_timer")
    if isinstance(old, threading.Timer) and old.is_alive():
        old.cancel()

    timer = threading.Timer(timeout_seconds, _fire)
    timer.daemon = True
    timer.name   = f"RingTimer-{campaign_id}"
    timer.start()
    local["_ring_timer"] = timer
    logger.info("[TIMER] Timeout de %ds agendado para campaign=%s SID=%s", timeout_seconds, campaign_id, call_sid)


# ── Event API (chamados pelos webhooks em twilio_voice.py) ───────────────────

def on_lead_answered(campaign_id: int, call_sid: str):
    """Lead atendeu e entrou na conference. Cancela ring timer → in_call."""
    campaign_id = int(campaign_id)

    # Marca atomicamente no Redis que este SID foi atendido (antes de qualquer lógica)
    # O ring timer checa este flag para não cancelar uma chamada já atendida.
    _mark_sid_answered(call_sid)

    sess = _get_session(campaign_id)
    if not sess:
        return

    local = _local_state(campaign_id)
    lock  = local.get("_lock")
    acquired = lock.acquire(timeout=5) if lock else False
    try:
        # Recarrega sessão após obter lock
        sess = _get_session(campaign_id)
        if not sess:
            return

        is_predictive = sess.get("dial_mode") == "predictive"
        concurrent    = sess.get("concurrent_sids", [])

        if is_predictive:
            if call_sid not in concurrent:
                logger.info("[EVENT] on_lead_answered (predictive): SID %s não está no lote — ignorando", call_sid)
                return
            _cancel_predictive_sids(
                campaign_id, keep_sid=call_sid,
                company_id=sess.get("company_id"),
                user_email=sess.get("user_email"),
            )
        else:
            if sess.get("current_call_sid") != call_sid:
                logger.info("[EVENT] on_lead_answered: SID %s não é o atual — ignorando", call_sid)
                return

        _cancel_ring_timer(sess)
        sess["current_call_sid"] = call_sid
        sess["status"] = "in_call"
        _save_session(campaign_id, sess)
        logger.info("[EVENT] Lead atendeu (SID=%s, mode=%s) — status=in_call", call_sid, sess.get("dial_mode", "auto"))
    finally:
        if acquired and lock:
            lock.release()


def on_call_ended(campaign_id: int, company_id: int, call_sid: str, disposition: str, delay: int = None, force_advance: bool = False):
    """Chamada encerrada por qualquer motivo. Limpa estado e agenda próxima discagem."""
    campaign_id = int(campaign_id)
    company_id  = int(company_id)

    sess = _get_session(campaign_id)
    if not sess:
        logger.warning("[EVENT] on_call_ended: sessão não encontrada para campaign=%s", campaign_id)
        return

    logger.info("[EVENT] on_call_ended: campaign=%s, sid=%s, disposition=%s, status=%s",
                campaign_id, call_sid, disposition, sess.get("status"))

    if sess.get("status") in ("paused", "stopped", "finished"):
        logger.info("[EVENT] on_call_ended ignorado — status=%s", sess.get("status"))
        return

    current_sid = sess.get("current_call_sid")
    if not current_sid or current_sid != call_sid:
        logger.info("[EVENT] on_call_ended: SID %s não é o atual (%s) — ignorando", call_sid, current_sid)
        return

    _cancel_ring_timer(sess)

    current_lead_id = sess.get("current_lead_id")
    if current_lead_id and disposition in ("no_answer", "busy", "voicemail", "failed"):
        lead = Lead.query.filter_by(id=current_lead_id, company_id=company_id).first()
        if lead:
            run_since = None
            try:
                run_since = datetime.fromisoformat(sess["started_at"])
            except Exception:
                pass
            next_phone = _next_phone_for_lead(lead, campaign_id, company_id, _since=run_since, mobile_only=sess.get("mobile_only", False))
            if next_phone:
                logger.info("[EVENT] Lead %s ainda tem phone %s → tentando próximo número", lead.id, next_phone)
                lead.status = "new"
                db.session.commit()
                sess["status"]           = "running"
                sess["current_call_sid"] = None
                sess["current_lead_id"]  = None
                _save_session(campaign_id, sess)
                dial_next_in_session(campaign_id, company_id, force=True)
                return

    if force_advance:
        logger.info("[EVENT] Avanço forçado (AMD): %s (%s)", call_sid, disposition)
        sess["status"]           = "running"
        sess["current_call_sid"] = None
        sess["current_lead_id"]  = None

        if current_lead_id:
            try:
                lead = Lead.query.filter_by(id=current_lead_id, company_id=company_id).first()
                if lead and lead.status not in ("completed", "exhausted", "invalid", "retry", "voicemail"):
                    lead.status = "exhausted"
                    db.session.commit()
            except Exception:
                pass

        _save_session(campaign_id, sess)
        _advance(campaign_id, company_id, delay=0)
        return

    if disposition == "answered":
        logger.info("[EVENT] Chamada %s atendida → pausando para classificação", call_sid)
        sess["status"]           = "paused"
        sess["current_call_sid"] = None
        _save_session(campaign_id, sess)
        try:
            campaign = Campaign.query.get(campaign_id)
            if campaign:
                campaign.status = "paused"
                db.session.commit()
        except Exception as exc:
            logger.error("[EVENT] Erro ao pausar campanha no DB: %s", exc)
        return

    logger.info("[EVENT] Chamada %s encerrada (%s) → avançando", call_sid, disposition)

    if current_lead_id and disposition in ("no_answer", "busy", "failed"):
        try:
            _lead = Lead.query.filter_by(id=current_lead_id, company_id=company_id).first()
            if _lead and _lead.status in ("dialing", "ringing"):
                _lead.status = disposition
                db.session.commit()
            # Enrolar follow-up para não-atendidos
            if _lead:
                try:
                    from app.api.routes.followup_routes import enroll_lead_in_followup
                    enroll_lead_in_followup(
                        company_id=company_id,
                        lead_id=current_lead_id,
                        campaign_id=campaign_id,
                        call_id=None,
                        disposition="nao_atendeu" if disposition in ("no_answer", "busy") else disposition,
                    )
                except Exception as _fe:
                    logger.debug("[DIALER] Erro enroll follow-up: %s", _fe)
        except Exception:
            db.session.rollback()

    sess["status"]           = "running"
    sess["current_call_sid"] = None
    _save_session(campaign_id, sess)
    _advance(campaign_id, company_id, delay=delay if delay else 2)


# ── Advance ───────────────────────────────────────────────────────────────────

def _advance(campaign_id: int, company_id: int, delay: int = 0):
    sess = _get_session(campaign_id)
    if not sess or sess.get("status") in ("paused", "stopped", "finished", "in_call"):
        return

    is_predictive = sess.get("dial_mode") == "predictive"

    def _do_dial():
        if is_predictive:
            dial_predictive_batch(campaign_id, company_id)
        else:
            dial_next_in_session(campaign_id, company_id)

    if delay <= 0:
        _do_dial()
        return

    try:
        app = _get_app()
    except Exception:
        return

    def _run():
        time.sleep(delay)
        with app.app_context():
            s = _get_session(campaign_id)
            if s and s.get("status") == "running":
                _do_dial()

    t = threading.Thread(target=_run, daemon=True, name=f"Advance-{campaign_id}")
    t.start()



def resume_auto_dialer_for_campaign(campaign_id, company_id, delay_override=None):
    """Ponto de entrada compatível com twilio_voice.py."""
    campaign_id = int(campaign_id)
    company_id  = int(company_id)

    sess = _get_session(campaign_id)
    if not sess:
        return

    if sess.get("status") in ("paused", "stopped", "finished", "in_call"):
        logger.info("[RESUME] Ignorado — status=%s", sess.get("status"))
        return

    delay = delay_override if delay_override is not None else 0
    sess["status"] = "running"
    _save_session(campaign_id, sess)
    _advance(campaign_id, company_id, delay=delay)


# ── Predictive dialing (AMD-03) ──────────────────────────────────────

def _count_available_agents(company_id: int) -> int:
    """Conta agentes com status que permite receber chamadas."""
    return (
        Agent.query
        .filter(Agent.company_id == company_id, Agent.status.in_(['available', 'online', 'ready']))
        .count()
    ) or 1


def _cancel_predictive_sids(campaign_id: int, keep_sid: str, company_id: int, user_email: str = None):
    """
    Cancela no Twilio todas as chamadas preditivas em voo EXCETO keep_sid.
    Chamado quando um lead atende no modo preditivo.
    """
    sess = _get_session(campaign_id)
    if not sess:
        return
    concurrent = list(sess.get('concurrent_sids', []))
    company    = Company.query.get(company_id)
    if not company:
        return
    try:
        svc = TwilioService.from_company(company, current_user_email=user_email)
    except Exception:
        return
    for sid in concurrent:
        if sid and sid != keep_sid:
            try:
                svc.client.calls(sid).update(status='completed')
                logger.info('[PREDICTIVE] Chamada excedente %s cancelada', sid)
            except Exception as e:
                logger.warning('[PREDICTIVE] Erro ao cancelar %s: %s', sid, e)
    sess['concurrent_sids'] = [keep_sid] if keep_sid else []
    _save_session(campaign_id, sess)


def dial_predictive_batch(campaign_id: int, company_id: int):
    """
    Dispara um lote de chamadas preditivas:
      N = round(agentes_disponíveis × predictive_ratio)
    Cada chamada é registrada em concurrent_sids.
    A primeira que atender (on_lead_answered) cancela as demais.
    """
    sess = _get_session(campaign_id)
    if not sess or sess.get('status') not in ('running',):
        return

    ratio    = float(sess.get('predictive_ratio', 1.5))
    n_agents = _count_available_agents(company_id)
    n_calls  = max(1, round(n_agents * ratio))
    # Desconta chamadas já em voo
    in_flight = len([s for s in sess.get('concurrent_sids', []) if s])
    to_dial   = max(0, n_calls - in_flight)

    logger.info('[PREDICTIVE] campaign=%s agents=%d ratio=%.1f batch=%d in_flight=%d',
                campaign_id, n_agents, ratio, n_calls, in_flight)

    for _ in range(to_dial):
        # Re-lê sessão a cada iteração para status atualizado
        s = _get_session(campaign_id)
        if not s or s.get('status') != 'running':
            break
        ok, msg = dial_next_in_session(campaign_id, company_id)
        if not ok:
            logger.info('[PREDICTIVE] Parou batch: %s', msg)
            break


# ── Core dial ─────────────────────────────────────────────────────────────────

def dial_next_in_session(campaign_id: int, company_id: int, force: bool = False, skip_current_id: int = None) -> tuple:
    """Dispara a próxima ligação. Thread-safe via Lock não-bloqueante por sessão."""
    campaign_id = int(campaign_id)
    company_id  = int(company_id)

    sess = _get_session(campaign_id)
    if not sess:
        return False, "sessão não existe"

    local = _local_state(campaign_id)
    lock: threading.Lock = local["_lock"]
    if not lock.acquire(blocking=False):
        logger.info("[DIALER] Lock ocupado para campaign=%s — descartando duplicata", campaign_id)
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

    # ── Verifica janela de discagem ───────────────────────────────────────
    campaign = Campaign.query.filter_by(id=campaign_id, company_id=company_id).first()
    if campaign:
        allowed, reason = campaign.is_within_dialing_window()
        if not allowed:
            logger.warning("[DIALER] Fora da janela de discagem: %s — pausando campanha", reason)
            sess["status"]        = "paused"
            sess["pause_reason"]  = "dialing_window"
            sess["pause_detail"]  = reason
            _save_session(campaign_id, sess)
            try:
                campaign.status = "paused"
                db.session.commit()
            except Exception:
                pass
            return False, f"Fora da janela de discagem: {reason}"

    ring_timeout = (campaign.ring_timeout_seconds if campaign and campaign.ring_timeout_seconds else 50)
    ring_timeout = max(20, min(90, ring_timeout))  # clamped: 20-90s

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

    # ── Priority lead (AMD recovery) ─────────────────────────────────────
    lead = None
    priority_lead_id = sess.pop("_priority_lead_id", None)
    if priority_lead_id:
        priority_lead = Lead.query.filter_by(id=priority_lead_id, company_id=company_id).first()
        if priority_lead and priority_lead.campaign_id == campaign_id:
            phone_check = _next_phone_for_lead(priority_lead, campaign_id, company_id, ignore_history=True)
            if phone_check:
                lead = priority_lead
                logger.info("[DIALER] Discando lead prioritário (AMD recovery): %s", priority_lead_id)

    # ── Callback queue ────────────────────────────────────────────────────
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

    # ── Itera até achar lead + telefone ──────────────────────────────────
    while True:
        if lead is None:
            sess["status"]           = "finished"
            sess["current_lead_id"]  = None
            sess["current_call_sid"] = None
            _save_session(campaign_id, sess)
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

        phone = _next_phone_for_lead(lead, campaign_id, company_id, _since=run_since, mobile_only=mobile_only, ignore_history=(cb is not None))
        if phone:
            # DNC check: FAIL-SAFE — se a verificação falhar, bloqueia o número
            # para evitar discagem indevida (compliance LGPD).
            dnc_blocked = False
            try:
                from app.models.dnc import DNCEntry
                dnc_blocked = DNCEntry.is_blocked(company_id, phone)
            except Exception as _dnc_err:
                logger.warning(
                    "[DNC] Erro ao verificar DNC para lead=%s phone=%s — bloqueando por segurança: %s",
                    lead.id, phone, _dnc_err,
                )
                dnc_blocked = True  # fail-safe: protege compliance

            if dnc_blocked:
                logger.info("[DIALER] Lead %s phone %s na lista DNC — pulando", lead.id, phone)
                lead.status = "exhausted"
                db.session.commit()
                skipped.add(lead.id)
                lead = _next_lead_query(campaign_id, company_id, skipped)
                continue
            break

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
        _save_session(campaign_id, sess)
        return False, "nenhum operador disponível — sessão pausada"

    # ── Twilio ────────────────────────────────────────────────────────────
    if not campaign:
        campaign = Campaign.query.get(campaign_id)
    company = Company.query.get(company_id)
    try:
        svc = TwilioService.from_company(company, current_user_email=sess.get("user_email"))
    except ValueError as e:
        return False, str(e)

    conf_name  = f"agent_bridge_{agent.id}"
    status_url = f"{public_base}/api/twilio/status"

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

    amd_hold_url     = f"{public_base}/api/twilio/amd-hold?c={conf_name}&lead_id={lead.id}&cid={campaign_id}"
    amd_callback_url = f"{public_base}/api/twilio/amd-callback?c={conf_name}"

    # AMD threshold configurável por campanha
    amd_threshold_ms = getattr(campaign, 'amd_duration_threshold_ms', 6000) or 6000

    # Caller ID rotation: usa pool da campanha se configurado
    caller_id = campaign.next_caller_id() if campaign else None
    if caller_id:
        db.session.commit()  # persiste o índice atualizado antes da chamada
    else:
        caller_id = svc.twilio_number

    try:
        result = svc.client.calls.create(
            to                     = phone,
            from_                  = caller_id,
            url                    = amd_hold_url,
            status_callback        = f"{status_url}?c={conf_name}",
            status_callback_event  = ["initiated", "ringing", "answered", "completed"],
            status_callback_method = "POST",
            machine_detection      = "Enable",
            async_amd              = "true",
            async_amd_status_callback         = amd_callback_url,
            async_amd_status_callback_method  = "POST",
            machine_detection_timeout              = 15,
            machine_detection_speech_threshold     = min(amd_threshold_ms, 2400),
            machine_detection_speech_end_threshold = 2500,
            machine_detection_silence_timeout      = 3000,
            timeout                = ring_timeout + 5,  # Twilio timeout levemente maior que o nosso
        )
    except InsufficientCreditError as credit_err:
        db.session.rollback()
        _cleanup_failed_conference(conf_name)
        try:
            lead.status = "new"
            db.session.commit()
        except Exception:
            db.session.rollback()
        sess["status"]       = "paused"
        sess["pause_reason"] = "insufficient_credit"
        _save_session(campaign_id, sess)
        logger.warning("[DIALER] Campanha %s pausada — saldo insuficiente", campaign_id)
        return False, str(credit_err)
    except Exception as exc:
        db.session.rollback()
        _cleanup_failed_conference(conf_name)
        logger.error("[DIALER] Erro Twilio lead %s (%s): %s", lead.id, phone, exc, exc_info=True)
        try:
            fail = Call(
                company_id=company_id, campaign_id=campaign_id, lead_id=lead.id,
                agent_id=agent.id, phone_dialed=phone, direction="outbound",
                status="failed", duration_seconds=0, attempt=last_attempt + 1,
            )
            db.session.add(fail)
            lead.status = "new"
            db.session.commit()
        except Exception:
            db.session.rollback()
        exc_str = str(exc).lower()
        is_config_error = any(k in exc_str for k in [
            "not yet verified", "not verified", "21210",
            "authentication", "auth", "credentials", "21608",
            "permission", "account suspended", "account is not active",
        ])
        if is_config_error:
            sess["status"]        = "paused"
            sess["pause_reason"]  = "twilio_config_error"
            sess["pause_detail"]  = str(exc)[:300]
            _save_session(campaign_id, sess)
            return False, f"Erro de configuração Twilio: {exc}"
        return _dial_locked(campaign_id, company_id, sess, force=True)

    # ── Sucesso ───────────────────────────────────────────────────────────
    db_call.call_sid = result.sid
    db_call.status   = "ringing"
    lead.status      = "dialing"
    update_pending_lead_call_sid(conf_name, result.sid)
    db.session.commit()

    bridge_item = get_conference_by_agent(agent.id)
    if bridge_item:
        bridge_item["status"] = "ringing_lead"
        from app.services.call_bridge import update_conference
        update_conference(conf_name, status="ringing_lead")

    all_phones = lead.get_all_phones()
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

    # Modo preditivo: mantém 'running' e rastreia SIDs em voo
    if sess.get("dial_mode") == "predictive":
        sids = list(sess.get("concurrent_sids", []))
        if result.sid not in sids:
            sids.append(result.sid)
        sess["concurrent_sids"] = sids
        sess["status"]          = "running"   # não bloqueia próxima chamada do lote

    _save_session(campaign_id, sess)


    _start_ring_timer(campaign_id, company_id, result.sid, sess, timeout_seconds=ring_timeout)

    logger.info("=" * 60)
    logger.info("[DISCANDO] Lead=%s | %s | %s | Campaign=%s | SID=%s | timeout=%ds",
                lead.id, lead.name, phone, campaign_id, result.sid, ring_timeout)
    logger.info("=" * 60)

    return True, conf_name


def _cleanup_failed_conference(conf_name: str):
    """Limpa estado de conferência após falha Twilio."""
    if conf_name.startswith("agent_bridge_"):
        item = get_conference_by_name(conf_name)
        if item:
            item["lead_id"]       = None
            item["db_call_id"]    = None
            item["lead_call_sid"] = None
            item["status"]        = "idle"
            from app.services.call_bridge import update_conference, _delete_conference
            update_conference(conf_name, lead_id=None, db_call_id=None, lead_call_sid=None, status="idle")
            ACTIVE_CONFERENCES_BY_NAME.pop(conf_name, None)
    else:
        clear_pending_conference(conf_name)


# ── Endpoints HTTP ────────────────────────────────────────────────────────────

@auto_dialer_bp.route("/start", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60, key_prefix="dialer_start")
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

    # Verifica janela de discagem antes de iniciar
    allowed, reason = campaign.is_within_dialing_window()
    if not allowed:
        return jsonify({"error": f"Fora da janela de discagem: {reason}"}), 400

    dialable_statuses = [
        "new", "novo", "tentativa", "tentando", "retry", "callback",
        "retornar", "qualified", "no_answer", "busy", "failed", "voicemail", "invalid_number"
    ]

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
        Call.query.filter(
            Call.campaign_id == campaign_id,
            Call.company_id  == g.company_id,
        ).update({"status": "reset"}, synchronize_session=False)
        db.session.flush()
        logger.info("[START] Campanha %s reiniciada", campaign_id)

    leads_total = Lead.query.filter(
        Lead.campaign_id == campaign_id,
        Lead.company_id  == g.company_id,
        Lead.status.in_(dialable_statuses),
    ).count()

    _new_session(
        campaign_id, g.company_id, campaign.name,
        interval_sec, leads_total, bool(campaign.mobile_only),
        user_email=getattr(g, 'user_email', None),
        dial_mode=campaign.dial_mode or 'auto',
        predictive_ratio=getattr(campaign, 'predictive_ratio', 1.5) or 1.5,
    )
    campaign.status = "running"
    db.session.commit()

    try:
        if campaign.dial_mode == 'predictive':
            # Preditivo: dispara lote inicial de chamadas em paralelo
            import threading as _th
            app = _get_app()
            def _batch():
                with app.app_context():
                    dial_predictive_batch(campaign_id, g.company_id)
            _th.Thread(target=_batch, daemon=True, name=f"PredictiveBatch-{campaign_id}").start()
            ok, msg = True, "predictive_batch_started"
        else:
            ok, msg = dial_next_in_session(campaign_id, g.company_id)
    except Exception as e:
        logger.error(f"[START] Erro interno: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": f"Erro interno ao iniciar: {str(e)}"}), 500

    return jsonify({
        "message":    "Discador automático iniciado",
        "ok":         ok,
        "first_dial": msg,
        "session":    _session_for_json(_get_session(campaign_id) or {}),
    }), 200


@auto_dialer_bp.route("/stop", methods=["POST"])
@require_auth
def stop_auto():
    body        = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = _get_session(campaign_id)
    if sess:
        _cancel_ring_timer(sess)
        sess["status"] = "stopped"
        _save_session(campaign_id, sess)

    try:
        company = Company.query.get(g.company_id)
        if company:
            user_email = sess.get("user_email") if sess else getattr(g, 'user_email', None)
            svc = TwilioService.from_company(company, current_user_email=user_email)
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
                c.status    = "no_answer"
                c.ended_at  = datetime.utcnow()
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

    sess = _get_session(campaign_id)
    if sess:
        sess["status"] = "paused"
        _cancel_ring_timer(sess)
        _save_session(campaign_id, sess)

    try:
        company = Company.query.get(g.company_id)
        if company:
            user_email = sess.get("user_email") if sess else getattr(g, 'user_email', None)
            svc = TwilioService.from_company(company, current_user_email=user_email)
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
                c.status   = "no_answer"
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

    # Verifica janela de discagem
    allowed, reason = campaign.is_within_dialing_window()
    if not allowed:
        return jsonify({"error": f"Fora da janela de discagem: {reason}"}), 400

    sess = _get_session(campaign_id)
    if not sess:
        leads_remaining = Lead.query.filter(
            Lead.campaign_id == campaign_id,
            Lead.company_id  == g.company_id,
            Lead.status.in_(["new", "novo"]),
        ).count()
        _new_session(
            campaign_id, g.company_id, campaign.name,
            3, leads_remaining, bool(campaign.mobile_only),
            user_email=getattr(g, 'user_email', None)
        )
        sess = _get_session(campaign_id)
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
        _save_session(campaign_id, sess)

    campaign.status = "running"
    db.session.commit()

    ok, msg = dial_next_in_session(campaign_id, g.company_id)
    return jsonify({
        "message": "Discador retomado",
        "ok":      ok,
        "msg":     msg,
        "session": _session_for_json(_get_session(campaign_id) or {}),
    }), 200


@auto_dialer_bp.route("/next", methods=["POST"])
@require_auth
def next_lead():
    body        = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = _get_session(campaign_id)
    if not sess or sess.get("company_id") != g.company_id:
        return jsonify({"error": "Sessão não encontrada"}), 404

    _cancel_ring_timer(sess)

    current_lead_id = sess.get("current_lead_id")
    current_sid     = sess.get("current_call_sid")

    company = Company.query.get(g.company_id)
    try:
        user_email = sess.get("user_email")
        svc = TwilioService.from_company(company, current_user_email=user_email)
        local = _local_state(campaign_id)
        if not isinstance(local.get("_cancelled_sids"), set):
            local["_cancelled_sids"] = set()
        active = Call.query.filter(
            Call.campaign_id == campaign_id,
            Call.status.in_(["ringing", "dialing", "waiting_agent", "in-progress", "answered", "agent_joined"]),
        ).all()
        for c in active:
            if c.call_sid:
                local["_cancelled_sids"].add(c.call_sid)
                try:
                    svc.client.calls(c.call_sid).update(status="completed")
                except Exception:
                    pass
            c.status   = "no_answer"
            c.ended_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        logger.warning("[NEXT] Erro ao cancelar chamadas: %s", e)

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
    _save_session(campaign_id, sess)

    ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True, skip_current_id=current_lead_id)
    return jsonify({
        "message": "Próximo lead",
        "ok":      ok,
        "msg":     msg,
        "session": _session_for_json(_get_session(campaign_id) or {}),
    }), 200


@auto_dialer_bp.route("/skip_phone", methods=["POST"])
@require_auth
def skip_phone():
    body        = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = _get_session(campaign_id)
    if not sess or sess.get("company_id") != g.company_id:
        return jsonify({"error": "Sessão não encontrada"}), 404

    current_lead_id = sess.get("current_lead_id")
    if not current_lead_id:
        return jsonify({"error": "Nenhum lead ativo"}), 400

    lead = Lead.query.filter_by(id=current_lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    _cancel_ring_timer(sess)
    current_sid = sess.get("current_call_sid")
    local       = _local_state(campaign_id)

    company = Company.query.get(g.company_id)
    try:
        user_email = sess.get("user_email")
        svc = TwilioService.from_company(company, current_user_email=user_email)
        if not isinstance(local.get("_cancelled_sids"), set):
            local["_cancelled_sids"] = set()
        for item in list(ACTIVE_CONFERENCES_BY_AGENT.values()):
            if item.get("campaign_id") == int(campaign_id):
                sid = item.get("lead_call_sid")
                if sid:
                    local["_cancelled_sids"].add(sid)
                    try:
                        svc.client.calls(sid).update(status="completed")
                    except Exception:
                        pass
                conf_name = item.get("conference_name", "")
                if conf_name.startswith("agent_bridge_"):
                    from app.services.call_bridge import update_conference
                    update_conference(conf_name,
                                      lead_id=None, db_call_id=None,
                                      lead_call_sid=None, audio_bridged=False,
                                      lead_answered_at=None, status="idle")
                    item.update({"lead_id": None, "db_call_id": None,
                                 "lead_call_sid": None, "audio_bridged": False,
                                 "lead_answered_at": None, "status": "idle"})
                    ACTIVE_CONFERENCES_BY_NAME.pop(conf_name, None)
                else:
                    clear_pending_conference(conf_name)
    except Exception as e:
        logger.warning("[SKIP-PHONE] Erro ao cancelar chamada: %s", e)

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

    run_since = None
    try:
        run_since = datetime.fromisoformat(sess["started_at"])
    except Exception:
        pass

    next_ph = _next_phone_for_lead(
        lead, campaign_id, g.company_id,
        _since=run_since, mobile_only=sess.get("mobile_only", False),
    )
    if not next_ph:
        lead.status = "no_answer"
        db.session.commit()
        sess["status"]           = "running"
        sess["current_lead_id"]  = None
        sess["current_call_sid"] = None
        _save_session(campaign_id, sess)
        ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True)
        return jsonify({"ok": ok, "msg": msg or "Todos os números tentados — próximo lead", "has_next_phone": False}), 200

    lead.status = "new"
    db.session.commit()

    sess["status"]           = "running"
    sess["current_lead_id"]  = None
    sess["current_call_sid"] = None
    _save_session(campaign_id, sess)

    ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True)
    return jsonify({
        "ok":             ok,
        "msg":            msg,
        "lead_id":        lead.id,
        "lead_name":      sess.get("current_lead_name") or lead.name,
        "phone":          sess.get("current_lead_phone") or "",
        "has_next_phone": True,
        "session":        _session_for_json(_get_session(campaign_id) or {}),
    }), 200


@auto_dialer_bp.route("/classified", methods=["POST"])
@require_auth
def lead_classified():
    body = request.get_json(silent=True) or {}
    campaign_id = body.get("campaign_id")
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    sess = _get_session(campaign_id)
    if not sess or sess.get("company_id") != g.company_id:
        return jsonify({"error": "Sessão não encontrada"}), 404

    current_lead_id  = sess.get("current_lead_id")
    current_call_sid = sess.get("current_call_sid")

    if current_call_sid:
        _clear_bridge_for_sid(current_call_sid)

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
                _since=run_since, mobile_only=sess.get("mobile_only", False),
            )

            if next_phone:
                logger.info("[CLASSIFIED] Lead %s tem próximo phone %s → discando", lead.id, next_phone)
                lead.status = "new"
                db.session.commit()
                sess["status"]           = "running"
                sess["current_call_sid"] = None
                sess["current_lead_id"]  = None
                _save_session(campaign_id, sess)
                ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True)
                return jsonify({"ok": ok, "msg": "Próximo número do mesmo lead", "next_phone": next_phone}), 200

    lead = Lead.query.filter_by(id=current_lead_id, company_id=g.company_id).first()
    if lead:
        lead.status = "new"
        db.session.commit()

    sess["status"]           = "running"
    sess["current_lead_id"]  = None
    sess["current_call_sid"] = None
    _save_session(campaign_id, sess)

    ok, msg = dial_next_in_session(campaign_id, g.company_id, force=True)
    return jsonify({"ok": ok, "msg": msg or "Próximo lead"}), 200


@auto_dialer_bp.route("/status/<int:campaign_id>", methods=["GET"])
@require_auth
def auto_status(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    sess     = _get_session(campaign_id)
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
