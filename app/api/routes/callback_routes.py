"""
Callback Queue API
==================
Blueprint : callback_bp
Prefix    : /api/callbacks

Endpoints
---------
GET    /api/callbacks           List pending callbacks (priority-sorted)
POST   /api/callbacks           Create callback manually
PATCH  /api/callbacks/<id>      Update priority / scheduled_for / notes
DELETE /api/callbacks/<id>      Cancel callback
"""
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.auth import require_auth, require_role
from app.core.enums import CallbackStatus
from app.extensions import db
from app.models.callback_queue import CallbackQueue

callback_bp = Blueprint("callbacks", __name__, url_prefix="/api/callbacks")


@callback_bp.route("", methods=["GET"])
@require_auth
def list_callbacks():
    status   = request.args.get("status", "pending")
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)

    q = CallbackQueue.query.filter_by(company_id=g.company_id)
    if status and status != "all":
        q = q.filter(CallbackQueue.status == status)

    total = q.count()
    items = (
        q.order_by(
            CallbackQueue.priority.desc(),
            CallbackQueue.scheduled_for.asc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify({
        "callbacks": [cb.to_dict() for cb in items],
        "total":     total,
        "page":      page,
        "per_page":  per_page,
    })


@callback_bp.route("", methods=["POST"])
@require_auth
@require_role("admin", "agent")
def create_callback():
    data = request.get_json() or {}
    lead_id     = data.get("lead_id")
    campaign_id = data.get("campaign_id")
    if not lead_id or not campaign_id:
        return jsonify({"error": "lead_id e campaign_id são obrigatórios"}), 400

    scheduled_raw = data.get("scheduled_for")
    try:
        scheduled = datetime.fromisoformat(scheduled_raw) if scheduled_raw else datetime.utcnow()
    except ValueError:
        return jsonify({"error": "scheduled_for inválido (ISO 8601)"}), 400

    cb = CallbackQueue(
        company_id    = g.company_id,
        lead_id       = lead_id,
        call_id       = data.get("call_id"),
        campaign_id   = campaign_id,
        priority      = int(data.get("priority") or 1),
        notes         = data.get("notes"),
        scheduled_for = scheduled,
        status        = CallbackStatus.PENDING.value,
    )
    db.session.add(cb)
    db.session.commit()
    return jsonify(cb.to_dict()), 201


@callback_bp.route("/<int:cb_id>", methods=["PATCH"])
@require_auth
@require_role("admin", "agent")
def update_callback(cb_id: int):
    cb = CallbackQueue.query.filter_by(id=cb_id, company_id=g.company_id).first()
    if not cb:
        return jsonify({"error": "Callback não encontrado"}), 404

    data = request.get_json() or {}
    if "priority" in data:
        cb.priority = max(1, min(3, int(data["priority"])))
    if "notes" in data:
        cb.notes = data["notes"]
    if "scheduled_for" in data:
        try:
            cb.scheduled_for = datetime.fromisoformat(data["scheduled_for"])
        except ValueError:
            return jsonify({"error": "scheduled_for inválido"}), 400

    db.session.commit()
    return jsonify(cb.to_dict())


@callback_bp.route("/<int:cb_id>", methods=["DELETE"])
@require_auth
@require_role("admin", "agent")
def cancel_callback(cb_id: int):
    cb = CallbackQueue.query.filter_by(id=cb_id, company_id=g.company_id).first()
    if not cb:
        return jsonify({"error": "Callback não encontrado"}), 404

    cb.status = CallbackStatus.CANCELED.value
    db.session.commit()
    return jsonify({"ok": True})
