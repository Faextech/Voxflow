from __future__ import annotations
from datetime import datetime

from app.extensions import db
from app.models.agent import Agent
from app.models.call import Call
from app.models.callback_queue import CallbackQueue
from app.core.enums import AgentStatus, CallStatus, CallbackStatus


class RoutingService:

    @staticmethod
    def find_available_agent():
        return (
            Agent.query
            .filter(Agent.status == AgentStatus.AVAILABLE.value)
            .order_by(Agent.id.asc())
            .first()
        )

    @staticmethod
    def reserve_agent(agent: Agent):
        agent.status = AgentStatus.RINGING.value
        agent.last_seen_at = datetime.utcnow()
        db.session.commit()
        return agent

    @staticmethod
    def release_agent(agent: Agent):
        agent.status = AgentStatus.AVAILABLE.value
        agent.last_seen_at = datetime.utcnow()
        db.session.commit()
        return agent

    @staticmethod
    def assign_call_to_agent(call: Call):
        agent = RoutingService.find_available_agent()

        if not agent:
            return None

        RoutingService.reserve_agent(agent)

        call.agent_id = agent.id
        call.status = CallStatus.OFFERED.value
        call.ringing_at = datetime.utcnow()

        db.session.commit()
        return agent

    @staticmethod
    def mark_call_accepted(call: Call, agent: Agent):
        call.status = CallStatus.IN_CALL.value
        call.answered_at = datetime.utcnow()

        agent.status = AgentStatus.IN_CALL.value
        agent.last_seen_at = datetime.utcnow()

        db.session.commit()
        return call

    @staticmethod
    def mark_call_rejected(call: Call, agent: Agent):
        call.status = CallStatus.REJECTED.value
        call.agent_id = None

        agent.status = AgentStatus.AVAILABLE.value
        agent.last_seen_at = datetime.utcnow()

        db.session.commit()
        return call

    @staticmethod
    def mark_call_completed(call: Call, agent: Agent | None = None, disposition: str | None = None):
        call.status = CallStatus.COMPLETED.value
        call.ended_at = datetime.utcnow()

        if disposition:
            call.disposition = disposition

        if call.answered_at and call.ended_at:
            call.duration_seconds = int((call.ended_at - call.answered_at).total_seconds())

        if agent:
            agent.status = AgentStatus.AVAILABLE.value
            agent.last_seen_at = datetime.utcnow()

        db.session.commit()
        return call

    @staticmethod
    def handle_no_available_agent(call: Call):
        call.status = CallStatus.CALLBACK.value

        callback = CallbackQueue(
            lead_id=call.lead_id,
            call_id=call.id,
            campaign_id=call.campaign_id,
            status=CallbackStatus.PENDING.value,
            scheduled_for=datetime.utcnow(),
            attempts=0,
            reserved_agent_id=None,
        )

        db.session.add(callback)
        db.session.commit()

        return callback