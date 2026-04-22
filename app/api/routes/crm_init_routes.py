from flask import Blueprint, jsonify, g
from app.extensions import db
from app.auth import require_auth
from app.models.pipeline import Pipeline, PipelineStage

crm_init_bp = Blueprint("crm_init", __name__, url_prefix="/api/crm")

_DEFAULT_STAGES = [
    {"name": "Novos Leads",      "position": 0, "color": "#6366f1", "prob": 5},
    {"name": "Em Contato",       "position": 1, "color": "#3b82f6", "prob": 15},
    {"name": "Qualificado",      "position": 2, "color": "#f59e0b", "prob": 40},
    {"name": "Reunião Agendada", "position": 3, "color": "#8b5cf6", "prob": 60, "is_meeting": True},
    {"name": "Proposta Enviada", "position": 4, "color": "#06b6d4", "prob": 75},
    {"name": "Ganho",            "position": 5, "color": "#22c55e", "prob": 100, "is_won": True},
    {"name": "Perdido",          "position": 6, "color": "#ef4444", "prob": 0,   "is_lost": True},
    {"name": "Não Atendeu",      "position": 7, "color": "#6b7280", "prob": 5},
    {"name": "Caixa Postal",     "position": 8, "color": "#9ca3af", "prob": 5},
    {"name": "Inválido",         "position": 9, "color": "#374151", "prob": 0,   "is_lost": True},
]


def _create_default_pipeline(company_id):
    """Cria a pipeline 'Comercial' com todas as etapas padrão."""
    pipeline = Pipeline(
        company_id  = company_id,
        name        = "Comercial",
        description = "Pipeline padrão de vendas criado automaticamente.",
        color       = "#6366f1",
        is_default  = True,
        position    = 0,
    )
    db.session.add(pipeline)
    db.session.flush()

    for s in _DEFAULT_STAGES:
        db.session.add(PipelineStage(
            pipeline_id         = pipeline.id,
            company_id          = company_id,
            name                = s["name"],
            position            = s["position"],
            color               = s["color"],
            default_probability = s.get("prob", 10),
            is_meeting          = s.get("is_meeting", False),
            is_won              = s.get("is_won", False),
            is_lost             = s.get("is_lost", False),
        ))

    db.session.commit()
    return pipeline


@crm_init_bp.route("/initialize", methods=["POST"])
@require_auth
def initialize_crm():
    """
    Garante que a empresa tenha ao menos uma pipeline.
    Se não houver nenhuma, cria a pipeline 'Comercial' padrão.
    """
    company_id = g.company_id
    existing = Pipeline.query.filter_by(company_id=company_id).first()

    if not existing:
        pipeline = _create_default_pipeline(company_id)
        return jsonify({
            "message": "CRM inicializado com sucesso",
            "pipeline_id": pipeline.id,
            "created": True,
        }), 201

    return jsonify({
        "message": "CRM já possui pipelines",
        "pipeline_id": existing.id,
        "created": False,
    }), 200


@crm_init_bp.route("/create-default-pipeline", methods=["POST"])
@require_auth
def create_default_pipeline():
    """
    Cria a pipeline 'Comercial' com todas as etapas padrão,
    mesmo que já existam outras pipelines.
    Útil para usuários que criaram pipelines manualmente antes
    de ter o padrão disponível.
    """
    company_id = g.company_id

    # Evita duplicar se já existe uma pipeline chamada "Comercial"
    already = Pipeline.query.filter_by(company_id=company_id, name="Comercial").first()
    if already:
        return jsonify({
            "message": "Pipeline 'Comercial' já existe",
            "pipeline_id": already.id,
            "created": False,
        }), 200

    pipeline = _create_default_pipeline(company_id)
    return jsonify({
        "message": "Pipeline 'Comercial' criada com sucesso",
        "pipeline_id": pipeline.id,
        "created": True,
    }), 201
