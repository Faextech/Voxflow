"""
Rotas de gerenciamento de usuários.
GET  /api/me           — perfil do usuário logado
PUT  /api/me           — atualiza nome / senha
GET  /api/users        — lista usuários da empresa (admin)
POST /api/users        — cria novo usuário (admin)
PUT  /api/users/<id>/role — altera role de um usuário (admin)
"""
from datetime import datetime

from flask import Blueprint, jsonify, request, g
from werkzeug.security import generate_password_hash

from app.auth import require_auth, require_role, generate_jwt_token
from app.extensions import db
from app.models.user import User
from app.models.agent import Agent

user_routes_bp = Blueprint("user_routes", __name__, url_prefix="/api")


def _serialize_user(u):
    return {
        "id":         u.id,
        "name":       u.name,
        "email":      u.email,
        "role":       u.role,
        "status":     u.status,
        "is_active":  u.status == "active",
        "agent_id":   u.agent_profile.id if u.agent_profile else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ─── /api/me ────────────────────────────────────────────────────────────────

@user_routes_bp.route("/me", methods=["GET"])
@require_auth
def get_me():
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404
    return jsonify(_serialize_user(user)), 200


@user_routes_bp.route("/me", methods=["PUT"])
@require_auth
def update_me():
    data = request.get_json(silent=True) or {}
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    if "name" in data and data["name"].strip():
        user.name = data["name"].strip()

    if data.get("password"):
        if len(data["password"]) < 6:
            return jsonify({"error": "Senha deve ter ao menos 6 caracteres"}), 400
        user.password_hash = generate_password_hash(data["password"], method='pbkdf2:sha256')

    db.session.commit()

    # Gera novo token com dados atualizados
    new_token = generate_jwt_token(user.id, user.company_id, user.role)

    return jsonify({
        "message": "Perfil atualizado",
        "user": _serialize_user(user),
        "token": new_token,
    }), 200


# ─── /api/users ─────────────────────────────────────────────────────────────

@user_routes_bp.route("/users", methods=["GET"])
@require_auth
def list_users():
    users = (
        User.query
        .filter_by(company_id=g.company_id)
        .order_by(User.created_at.asc())
        .all()
    )
    return jsonify([_serialize_user(u) for u in users]), 200


@user_routes_bp.route("/users", methods=["POST"])
@require_auth
@require_role("admin")
def create_user():
    data = request.get_json(silent=True) or {}

    email    = (data.get("email") or "").strip().lower()
    name     = (data.get("name") or "").strip()
    password = data.get("password") or ""
    role     = data.get("role", "agent")

    if not email:
        return jsonify({"error": "email é obrigatório"}), 400
    if not name:
        return jsonify({"error": "name é obrigatório"}), 400
    if len(password) < 6:
        return jsonify({"error": "Senha deve ter ao menos 6 caracteres"}), 400
    if role not in ("admin", "agent", "supervisor"):
        return jsonify({"error": "role inválida"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "E-mail já cadastrado"}), 400

    user = User(
        company_id    = g.company_id,
        name          = name,
        email         = email,
        password_hash = generate_password_hash(password, method='pbkdf2:sha256'),
        role          = role,
        status        = "active",
    )
    db.session.add(user)
    db.session.flush()

    # Cria perfil Agent para todos os roles (necessário para o webphone)
    agent = Agent(company_id=g.company_id, user_id=user.id, status="offline")
    db.session.add(agent)

    db.session.commit()

    return jsonify({
        "message": "Usuário criado com sucesso",
        "user": _serialize_user(user),
    }), 201


@user_routes_bp.route("/users/<int:user_id>/role", methods=["PUT"])
@require_auth
@require_role("admin")
def update_user_role(user_id):
    """Altera a role de um usuário da mesma empresa."""
    data = request.get_json(silent=True) or {}
    new_role = data.get("role", "").strip()

    if new_role not in ("admin", "agent", "supervisor"):
        return jsonify({"error": "role inválida. Use: admin, agent, supervisor"}), 400

    user = User.query.filter_by(id=user_id, company_id=g.company_id).first()
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    old_role = user.role
    user.role = new_role

    # Se promovido a agente, cria perfil Agent se não existir
    if new_role == "agent" and not user.agent_profile:
        agent = Agent(company_id=g.company_id, user_id=user.id, status="offline")
        db.session.add(agent)

    db.session.commit()

    return jsonify({
        "message": f"Role alterada de '{old_role}' para '{new_role}'",
        "user": _serialize_user(user),
    }), 200


@user_routes_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_user(user_id):
    """Remove um usuário da empresa (não pode remover a si mesmo)."""
    if user_id == g.user_id:
        return jsonify({"error": "Você não pode remover sua própria conta"}), 400

    user = User.query.filter_by(id=user_id, company_id=g.company_id).first()
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "Usuário removido"}), 200


# ─── /api/me/promote — qualquer usuário autenticado promove a si mesmo a admin
# Útil para o primeiro usuário de uma empresa que foi criado sem o papel correto
@user_routes_bp.route("/me/promote-admin", methods=["POST"])
@require_auth
def promote_self_to_admin():
    """
    Permite que o único admin de uma empresa se auto-promova.
    Se já existe um admin na empresa, apenas outros admins podem usar.
    """
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    # Verifica se já há outros admins
    other_admins = User.query.filter(
        User.company_id == g.company_id,
        User.role == "admin",
        User.id != g.user_id,
    ).count()

    # Se já há outro admin e este usuário não é admin, proíbe
    if other_admins > 0 and g.user_role != "admin":
        return jsonify({"error": "Apenas o administrador pode alterar roles"}), 403

    user.role = "admin"
    db.session.commit()

    # Novo token com role atualizada
    new_token = generate_jwt_token(user.id, user.company_id, "admin")

    return jsonify({
        "message": "Usuário promovido a administrador",
        "token": new_token,
        "role": "admin",
    }), 200
