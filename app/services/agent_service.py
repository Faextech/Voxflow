from datetime import datetime

from app.extensions import db
from app.models import Agent, User


class AgentService:
    VALID_STATUS = {
        'offline',
        'online',
        'paused',
        'ringing',
        'in_call'
    }

    def get_agent_by_user_id(self, user_id):
        return Agent.query.filter_by(user_id=user_id).first()

    def create_agent_for_user(self, user_id, company_id, extension=None):
        existing = self.get_agent_by_user_id(user_id)
        if existing:
            return existing

        agent = Agent(
            user_id=user_id,
            company_id=company_id,
            extension=extension,
            status='offline',
            last_seen_at=datetime.utcnow()
        )

        db.session.add(agent)
        db.session.commit()
        return agent

    def set_status(self, agent_id, status):
        if status not in self.VALID_STATUS:
            raise ValueError(f'Status inválido: {status}')

        agent = Agent.query.get(agent_id)
        if not agent:
            raise ValueError('Agent não encontrado.')

        agent.status = status
        agent.last_seen_at = datetime.utcnow()
        db.session.commit()

        return agent

    def set_status_by_user(self, user_id, status):
        if status not in self.VALID_STATUS:
            raise ValueError(f'Status inválido: {status}')

        agent = Agent.query.filter_by(user_id=user_id).first()
        if not agent:
            raise ValueError('Agent não encontrado para este usuário.')

        agent.status = status
        agent.last_seen_at = datetime.utcnow()
        db.session.commit()

        return agent

    def get_available_agent(self, company_id=None):
        query = Agent.query.filter_by(status='online')

        if company_id:
            query = query.filter_by(company_id=company_id)

        return query.order_by(Agent.last_seen_at.asc()).first()

    def list_agents(self, company_id=None):
        query = Agent.query

        if company_id:
            query = query.filter_by(company_id=company_id)

        return query.order_by(Agent.created_at.desc()).all()

    def ensure_agent_profile(self, user_id):
        user = User.query.get(user_id)
        if not user:
            raise ValueError('Usuário não encontrado.')

        agent = Agent.query.filter_by(user_id=user.id).first()
        if agent:
            return agent

        agent = Agent(
            user_id=user.id,
            company_id=user.company_id,
            status='offline',
            last_seen_at=datetime.utcnow()
        )

        db.session.add(agent)
        db.session.commit()
        return agent