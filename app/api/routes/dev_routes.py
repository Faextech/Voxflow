from __future__ import annotations
from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import Integer, String, Boolean, DateTime

from app.auth import require_auth, require_role
from app.extensions import db
from app.models.company import Company
from app.models.user import User
from app.models.agent import Agent
from app.models.pipeline import Pipeline, PipelineStage

dev_bp = Blueprint("dev", __name__, url_prefix="/api/dev")


def _random_text(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def _set_if_exists(obj, field_name, value):
    if hasattr(obj.__class__, field_name):
        setattr(obj, field_name, value)


def _fill_required_fields(obj, explicit_values: dict | None = None):
    explicit_values = explicit_values or {}

    for column in obj.__table__.columns:
        name = column.name

        if name in explicit_values:
            setattr(obj, name, explicit_values[name])
            continue

        if name == "id":
            continue

        current_value = getattr(obj, name, None)
        if current_value is not None:
            continue

        has_default = column.default is not None or column.server_default is not None
        is_required = not column.nullable and not has_default

        if not is_required:
            continue

        col_type = column.type

        if isinstance(col_type, String):
            lowered = name.lower()

            if "email" in lowered:
                setattr(obj, name, f"{_random_text('dev')}@test.com")
            elif "password" in lowered or "hash" in lowered:
                setattr(obj, name, _random_text("senha"))
            elif "cnpj" in lowered:
                setattr(obj, name, "00.000.000/0001-00")
            elif "phone" in lowered or "whatsapp" in lowered:
                setattr(obj, name, "11999999999")
            elif "plan" in lowered:
                setattr(obj, name, "basic")
            elif "status" in lowered:
                setattr(obj, name, "offline")
            elif "name" in lowered:
                setattr(obj, name, _random_text("nome"))
            else:
                setattr(obj, name, _random_text(name))

        elif isinstance(col_type, Integer):
            setattr(obj, name, 1)

        elif isinstance(col_type, Boolean):
            setattr(obj, name, False)

        elif isinstance(col_type, DateTime):
            setattr(obj, name, datetime.utcnow())


@dev_bp.route("/create-agent-full", methods=["POST"])
def create_agent_full():
    try:
        # 1) COMPANY
        company = Company()
        _fill_required_fields(company)
        _set_if_exists(company, "name", "Empresa Teste NexDial")
        _set_if_exists(company, "plan", "basic")

        db.session.add(company)
        db.session.flush()

        # 2) USER
        user = User()
        _fill_required_fields(
            user,
            {
                "company_id": company.id
            }
        )

        _set_if_exists(user, "company_id", company.id)
        _set_if_exists(user, "name", "Operador Teste")
        _set_if_exists(user, "email", f"operador_{uuid4().hex[:6]}@teste.com")

        if hasattr(user, "set_password") and callable(getattr(user, "set_password")):
            user.set_password("123456")
        else:
            if hasattr(User, "password_hash"):
                user.password_hash = _random_text("hash123")

        db.session.add(user)
        db.session.flush()

        # 3) AGENT
        agent = Agent()
        _fill_required_fields(
            agent,
            {
                "company_id": company.id,
                "user_id": user.id,
                "status": "offline"
            }
        )

        _set_if_exists(agent, "company_id", company.id)
        _set_if_exists(agent, "user_id", user.id)
        _set_if_exists(agent, "status", "offline")
        _set_if_exists(agent, "extension", "1001")
        _set_if_exists(agent, "sip_username", "1001")
        _set_if_exists(agent, "sip_password", "123456")

        db.session.add(agent)
        db.session.commit()

        return jsonify({
            "message": "company, user e agent criados com sucesso",
            "company_id": company.id,
            "user_id": user.id,
            "agent_id": agent.id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "falha ao criar dados de teste",
            "details": str(e)
        }), 500


def _create_default_pipeline(company_id: int) -> dict:
    """
    Cria o pipeline padrão "Vendas" com 4 estágios para uma empresa.
    Ignora silenciosamente se já existir um pipeline padrão.
    Retorna dict com status e pipeline_id (ou None se já existia).
    """
    existing = Pipeline.query.filter_by(company_id=company_id, is_default=True).first()
    if existing:
        return {"created": False, "pipeline_id": existing.id, "reason": "já existe"}

    pipeline = Pipeline(
        company_id  = company_id,
        name        = "Vendas",
        description = "Pipeline padrão de vendas",
        color       = "#6366f1",
        is_default  = True,
        position    = 0,
    )
    db.session.add(pipeline)
    db.session.flush()

    for i, nome in enumerate(["Novo", "Em Contato", "Qualificado", "Fechado"]):
        db.session.add(PipelineStage(
            pipeline_id         = pipeline.id,
            company_id          = company_id,
            name                = nome,
            position            = i,
            color               = "#6366f1",
            is_won              = (nome == "Fechado"),
            default_probability = [10, 30, 70, 100][i],
        ))

    db.session.commit()
    return {"created": True, "pipeline_id": pipeline.id}


@dev_bp.route("/init-pipeline", methods=["POST"])
@require_auth
@require_role("admin")
def init_pipeline():
    """
    POST /api/dev/init-pipeline
    Cria o pipeline padrão "Vendas" para a empresa do usuário autenticado.
    Idempotente — não duplica se já existir.
    """
    from flask import g
    result = _create_default_pipeline(g.company_id)
    return jsonify({
        "message": "Pipeline inicializado" if result["created"] else "Pipeline já existe",
        **result,
    }), 200


@dev_bp.route("/init-pipeline/all", methods=["POST"])
@require_auth
@require_role("admin")
def init_pipeline_all():
    """
    POST /api/dev/init-pipeline/all
    Cria pipelines padrão para TODAS as empresas sem pipeline padrão.
    Útil para migrar empresas criadas antes dessa feature.
    Atenção: super_admin only (valida role no payload).
    """
    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "yes":
        return jsonify({
            "error": "Envie {'confirm': 'yes'} no body para confirmar",
        }), 400

    companies = Company.query.all()
    results = []
    for company in companies:
        try:
            res = _create_default_pipeline(company.id)
            results.append({"company_id": company.id, "company": company.name, **res})
        except Exception as exc:
            db.session.rollback()
            results.append({"company_id": company.id, "company": company.name, "error": str(exc)})

    created = sum(1 for r in results if r.get("created"))
    return jsonify({
        "message": f"{created} pipeline(s) criado(s) de {len(companies)} empresa(s)",
        "results": results,
    }), 200