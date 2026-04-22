from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.agent import Agent
from app.core.enums import AgentStatus

operator_bp = Blueprint("operator", __name__, url_prefix="/api/operator")


@operator_bp.route("/status", methods=["POST"])
def update_status():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "body JSON inválido ou ausente",
            "example": {
                "agent_id": 1,
                "status": "available"
            }
        }), 400

    agent_id = data.get("agent_id")
    new_status = data.get("status")

    if not agent_id or not new_status:
        return jsonify({"error": "agent_id e status são obrigatórios"}), 400

    if new_status not in AgentStatus.values():
        return jsonify({
            "error": "status inválido",
            "allowed": AgentStatus.values()
        }), 400

    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({"error": "operador não encontrado"}), 404

    agent.status = new_status
    agent.last_seen_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": "status atualizado",
        "agent": {
            "id": agent.id,
            "status": agent.status,
            "user_id": agent.user_id,
            "company_id": agent.company_id
        }
    }), 200


@operator_bp.route("/available", methods=["GET"])
def get_available_agents():
    agents = Agent.query.filter(
        Agent.status == AgentStatus.AVAILABLE.value
    ).all()

    return jsonify([
        {
            "id": a.id,
            "status": a.status,
            "extension": a.extension,
            "user_id": a.user_id,
            "company_id": a.company_id
        }
        for a in agents
    ]), 200


@operator_bp.route("/all", methods=["GET"])
def get_all_agents():
    agents = Agent.query.all()

    return jsonify([
        {
            "id": a.id,
            "status": a.status,
            "extension": a.extension,
            "sip_username": a.sip_username,
            "user_id": a.user_id,
            "company_id": a.company_id
        }
        for a in agents
    ]), 200