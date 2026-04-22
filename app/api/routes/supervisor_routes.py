from flask import Blueprint, jsonify, g
from app.models.agent import Agent
from app.models.user import User
from app.services.call_bridge import ACTIVE_CONFERENCES_BY_NAME
from app.extensions import db
from app.auth import require_auth

supervisor_bp = Blueprint("supervisor", __name__, url_prefix="/api/supervisor")

@supervisor_bp.route("/realtime", methods=["GET"])
@require_auth
def realtime_status():
    """
    Retorna o estado em tempo real de todos os operadores e conferências ativas.
    Apenas para administradores do mesmo tenant.
    """
    if g.user_role not in ('admin', 'supervisor'):
        return jsonify({"error": "Acesso negado. Apenas administradores podem acessar o supervisor."}), 403

    # Filtrar apenas agentes da mesma empresa
    agents = db.session.query(Agent).join(User).filter(User.company_id == g.company_id).all()
    
    # Mapear conferências por agente para facilitar o front-end
    active_conf_by_agent = {}
    for conf_name, data in ACTIVE_CONFERENCES_BY_NAME.items():
        aid = data.get("agent_id")
        if aid:
            active_conf_by_agent[aid] = {
                "conference_name": conf_name,
                "status": data.get("status"),
                "lead_name": data.get("lead_name"),
                "phone_number": data.get("phone_number"),
                "created_at": data.get("created_at"),
                "lead_answered_at": data.get("lead_answered_at")
            }

    agents_list = []
    for a in agents:
        agents_list.append({
            "id": a.id,
            "name": a.user.name, # Usa o nome do User vinculado
            "status": a.status or "offline",
            "last_active": a.last_seen_at.isoformat() if a.last_seen_at else None,
            "active_call": active_conf_by_agent.get(a.id)
        })

    return jsonify({
        "agents": agents_list,
        "total_active_conferences": len(ACTIVE_CONFERENCES_BY_NAME)
    }), 200
