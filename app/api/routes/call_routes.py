from flask import Blueprint, jsonify

from app.models.call import Call
from app.models.agent import Agent
from app.services.routing_service import RoutingService

call_bp = Blueprint("call", __name__, url_prefix="/api/call")


@call_bp.route("/assign/<int:call_id>", methods=["POST"])
def assign_call(call_id):
    call = Call.query.get(call_id)

    if not call:
        return jsonify({"error": "chamada não encontrada"}), 404

    agent = RoutingService.assign_call_to_agent(call)

    if not agent:
        RoutingService.handle_no_available_agent(call)
        return jsonify({
            "message": "nenhum operador disponível, enviado para callback",
            "call_id": call.id,
            "status": call.status
        }), 200

    return jsonify({
        "message": "chamada atribuída",
        "call_id": call.id,
        "agent_id": agent.id,
        "status": call.status
    }), 200


@call_bp.route("/accept/<int:call_id>", methods=["POST"])
def accept_call(call_id):
    call = Call.query.get(call_id)

    if not call or not call.agent_id:
        return jsonify({"error": "chamada inválida"}), 400

    agent = Agent.query.get(call.agent_id)
    if not agent:
        return jsonify({"error": "operador não encontrado"}), 404

    RoutingService.mark_call_accepted(call, agent)

    return jsonify({
        "message": "chamada aceita",
        "call_id": call.id,
        "agent_id": agent.id,
        "status": call.status
    }), 200


@call_bp.route("/reject/<int:call_id>", methods=["POST"])
def reject_call(call_id):
    call = Call.query.get(call_id)

    if not call or not call.agent_id:
        return jsonify({"error": "chamada inválida"}), 400

    agent = Agent.query.get(call.agent_id)
    if not agent:
        return jsonify({"error": "operador não encontrado"}), 404

    RoutingService.mark_call_rejected(call, agent)

    return jsonify({
        "message": "chamada rejeitada",
        "call_id": call.id,
        "status": call.status
    }), 200


@call_bp.route("/all", methods=["GET"])
def get_calls():
    calls = Call.query.all()

    return jsonify([
        {
            "id": c.id,
            "company_id": c.company_id,
            "campaign_id": c.campaign_id,
            "lead_id": c.lead_id,
            "agent_id": c.agent_id,
            "phone_dialed": c.phone_dialed,
            "status": c.status,
            "direction": c.direction,
            "answered_by": c.answered_by,
            "duration_seconds": c.duration_seconds,
            "attempt": c.attempt,
            "disposition": c.disposition,
            "hangup_cause": c.hangup_cause
        }
        for c in calls
    ]), 200