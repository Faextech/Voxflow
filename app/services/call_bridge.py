"""
Call Bridge — estado de conferências ativas.
Persiste no Redis quando disponível; cai para dicts in-memory como fallback.
Isso permite múltiplos workers Gunicorn compartilharem estado.
"""
import logging
from datetime import datetime

from app.services import redis_service

logger = logging.getLogger(__name__)

_CONF_TTL = 3600  # 1h — TTL Redis para conferências
_CONF_PREFIX = "voxflow:conf:name:"
_AGENT_PREFIX = "voxflow:conf:agent:"

# Fallback in-memory (usado quando Redis não disponível)
ACTIVE_CONFERENCES_BY_NAME: dict = {}
ACTIVE_CONFERENCES_BY_AGENT: dict = {}


def _save_conference(item: dict):
    """Persiste conferência no Redis e mantém dicts in-memory sincronizados."""
    name = item.get("conference_name")
    agent_id = item.get("agent_id")
    if name:
        redis_service.set(f"{_CONF_PREFIX}{name}", item, ex=_CONF_TTL)
        ACTIVE_CONFERENCES_BY_NAME[name] = item
    if agent_id is not None:
        redis_service.set(f"{_AGENT_PREFIX}{agent_id}", item, ex=_CONF_TTL)
        ACTIVE_CONFERENCES_BY_AGENT[agent_id] = item


def _load_conference_by_name(conference_name: str) -> dict:
    """Carrega do Redis se não estiver em memória (ex: após restart de worker)."""
    if conference_name in ACTIVE_CONFERENCES_BY_NAME:
        return ACTIVE_CONFERENCES_BY_NAME[conference_name]
    item = redis_service.get(f"{_CONF_PREFIX}{conference_name}")
    if item and isinstance(item, dict):
        ACTIVE_CONFERENCES_BY_NAME[conference_name] = item
        agent_id = item.get("agent_id")
        if agent_id is not None:
            ACTIVE_CONFERENCES_BY_AGENT[agent_id] = item
        return item
    return None


def _load_conference_by_agent(agent_id) -> dict:
    """Carrega do Redis se não estiver em memória."""
    if agent_id in ACTIVE_CONFERENCES_BY_AGENT:
        return ACTIVE_CONFERENCES_BY_AGENT[agent_id]
    item = redis_service.get(f"{_AGENT_PREFIX}{agent_id}")
    if item and isinstance(item, dict):
        ACTIVE_CONFERENCES_BY_AGENT[agent_id] = item
        name = item.get("conference_name")
        if name:
            ACTIVE_CONFERENCES_BY_NAME[name] = item
        return item
    return None


def _delete_conference(conference_name: str, agent_id=None):
    redis_service.delete(f"{_CONF_PREFIX}{conference_name}")
    ACTIVE_CONFERENCES_BY_NAME.pop(conference_name, None)
    if agent_id is not None:
        redis_service.delete(f"{_AGENT_PREFIX}{agent_id}")
        ACTIVE_CONFERENCES_BY_AGENT.pop(agent_id, None)


def register_pending_conference(
    *,
    conference_name,
    agent_id,
    lead_id,
    phone_number,
    lead_name=None,
    company_name=None,
    campaign_id=None,
    company_id=None,
    db_call_id=None,
    lead_call_sid=None,
    amd_enabled=False,
    user_email=None,
):
    # Herda agent_leg_call_sid se conferência já existia
    existing = _load_conference_by_name(conference_name)
    agent_leg = existing.get("agent_leg_call_sid") if existing else None

    if existing and existing.get("lead_id") != lead_id:
        logger.warning(
            "[BRIDGE] Conference %s: Lead %s substituído por Lead %s — phone: %s",
            conference_name, existing.get("lead_id"), lead_id, phone_number
        )

    item = {
        "conference_name":   conference_name,
        "agent_id":          agent_id,
        "lead_id":           lead_id,
        "phone_number":      phone_number,
        "user_email":        user_email,
        "lead_name":         lead_name,
        "company_name":      company_name,
        "campaign_id":       campaign_id,
        "company_id":        company_id,
        "db_call_id":        db_call_id,
        "lead_call_sid":     lead_call_sid,
        "agent_leg_call_sid": agent_leg,
        "amd_enabled":       amd_enabled,
        "amd_uncertain":     True,
        "audio_bridged":     False,
        "status":            "dialing",
        "created_at":        datetime.utcnow().isoformat(),
    }
    _save_conference(item)
    return item


def update_pending_lead_call_sid(conference_name: str, lead_call_sid: str):
    item = _load_conference_by_name(conference_name)
    if not item:
        return
    item["lead_call_sid"] = lead_call_sid
    _save_conference(item)


def clear_pending_conference(conference_name: str):
    item = _load_conference_by_name(conference_name)
    if item:
        _delete_conference(conference_name, agent_id=item.get("agent_id"))
    return item


def get_conference_by_agent(agent_id) -> dict:
    return _load_conference_by_agent(agent_id)


def get_conference_by_name(conference_name: str) -> dict:
    return _load_conference_by_name(conference_name)


def update_conference(conference_name: str, **kwargs):
    """Atualiza campos de uma conferência existente e persiste no Redis."""
    item = _load_conference_by_name(conference_name)
    if not item:
        return None
    item.update(kwargs)
    _save_conference(item)
    return item
