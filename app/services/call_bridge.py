from datetime import datetime

ACTIVE_CONFERENCES_BY_NAME = {}
ACTIVE_CONFERENCES_BY_AGENT = {}


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
    from datetime import datetime
    import logging
    logger = logging.getLogger(__name__)
    
    # Inherit existing agent leg
    existing = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)
    agent_leg = existing.get("agent_leg_call_sid") if existing else None
    
    # Verificar se já existe um lead diferente nesta conference (mesmo número)
    if existing and existing.get("lead_id") != lead_id:
        old_lead_id = existing.get("lead_id")
        logger.warning(
            "[BRIDGE] Conference %s: Lead %s está sendo substituído por Lead %s - Telefone: %s",
            conference_name, old_lead_id, lead_id, phone_number
        )

    item = {
        "conference_name": conference_name,
        "agent_id": agent_id,
        "lead_id": lead_id,
        "phone_number": phone_number,
        "user_email": user_email,
        "lead_name": lead_name,
        "company_name": company_name,
        "campaign_id": campaign_id,
        "company_id": company_id,
        "db_call_id": db_call_id,
        "lead_call_sid": lead_call_sid,
        "agent_leg_call_sid": agent_leg,
        "amd_enabled": amd_enabled,
        "amd_uncertain": True,      # sempre incerto até AMD confirmar humano
        "audio_bridged": False,     # só True após agente entrar na ponte
        "status": "dialing",  # será "answered_waiting_agent" quando o lead entrar na conference
        "created_at": datetime.utcnow().isoformat(),
    }
    ACTIVE_CONFERENCES_BY_NAME[conference_name] = item
    ACTIVE_CONFERENCES_BY_AGENT[agent_id] = item
    return item


def update_pending_lead_call_sid(conference_name, lead_call_sid):
    item = ACTIVE_CONFERENCES_BY_NAME.get(conference_name)
    if not item:
        return
    item["lead_call_sid"] = lead_call_sid


def clear_pending_conference(conference_name):
    item = ACTIVE_CONFERENCES_BY_NAME.pop(conference_name, None)
    if item:
        ACTIVE_CONFERENCES_BY_AGENT.pop(item["agent_id"], None)
    return item