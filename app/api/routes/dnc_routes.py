from flask import Blueprint, jsonify, request, g

from app.auth import require_auth, require_role
from app.extensions import db
from app.models.dnc import DNCEntry

dnc_bp = Blueprint("dnc", __name__, url_prefix="/api/dnc")


@dnc_bp.route("", methods=["GET"])
@require_auth
@require_role("admin")
def list_dnc():
    """Lista entradas DNC da empresa com paginação."""
    page     = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    entries  = (
        DNCEntry.query
        .filter_by(company_id=g.company_id)
        .order_by(DNCEntry.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        "total": entries.total,
        "page":  page,
        "items": [
            {"id": e.id, "phone": e.phone_e164, "reason": e.reason,
             "created_at": e.created_at.isoformat()}
            for e in entries.items
        ],
    })


@dnc_bp.route("", methods=["POST"])
@require_auth
@require_role("admin")
def add_dnc():
    """Adiciona um ou mais números ao DNC manualmente."""
    data   = request.get_json(silent=True) or {}
    phones = data.get("phones") or ([data.get("phone")] if data.get("phone") else [])
    reason = data.get("reason", "manual")

    if not phones:
        return jsonify({"error": "phones é obrigatório"}), 400

    added = []
    for phone in phones:
        if phone:
            normalized = DNCEntry.add(g.company_id, phone, reason=reason, added_by=g.user_id)
            added.append(normalized)

    return jsonify({"added": added, "count": len(added)}), 201


@dnc_bp.route("/<int:entry_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def remove_dnc(entry_id):
    """Remove uma entrada do DNC."""
    entry = DNCEntry.query.filter_by(id=entry_id, company_id=g.company_id).first()
    if not entry:
        return jsonify({"error": "Entrada não encontrada"}), 404
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"message": "Número removido do DNC"}), 200


@dnc_bp.route("/check", methods=["GET"])
@require_auth
def check_dnc():
    """Verifica se um número está na lista DNC. ?phone=+5511999999999"""
    phone = (request.args.get("phone") or "").strip()
    if not phone:
        return jsonify({"error": "phone é obrigatório"}), 400
    blocked = DNCEntry.is_blocked(g.company_id, phone)
    return jsonify({"phone": phone, "blocked": blocked})
