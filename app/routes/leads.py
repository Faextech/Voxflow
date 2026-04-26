import pandas as pd
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from app.auth import require_auth, require_role
from app.extensions import db
from app.models import Campaign, Lead, Call
from app.models.company import Company
from app.models.deal import Deal
from app.models.pipeline import Pipeline, PipelineStage
from app.services.twilio_service import TwilioService, normalize_phone_br, InsufficientCreditError

leads_bp = Blueprint("leads", __name__)


# ─────────────────────────────────────────────
# PADRÃO GERAL DE TENANT ISOLATION
# Toda query usa .filter_by(company_id=g.company_id) ou
# .filter(Model.company_id == g.company_id).
# g.company_id vem do JWT via @require_auth — não confiar no body/args.
# ─────────────────────────────────────────────


def serialize_campaign(campaign):
    total  = Lead.query.filter_by(campaign_id=campaign.id, company_id=campaign.company_id).count()
    pending = Lead.query.filter(
        Lead.campaign_id == campaign.id,
        Lead.company_id  == campaign.company_id,
        Lead.status.in_(["new", "novo"]),
    ).count()
    return {
        "id":              campaign.id,
        "company_id":      campaign.company_id,
        "name":            campaign.name,
        "description":     campaign.description,
        "status":          campaign.status,
        "dial_mode":       campaign.dial_mode,
        "retry_limit":     campaign.retry_limit,
        "mobile_only":     bool(campaign.mobile_only),
        "leads_total":     total,
        "leads_pending":   pending,
        "created_at":      campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at":      campaign.updated_at.isoformat() if campaign.updated_at else None,
        "default_pipeline_id": campaign.default_pipeline_id,
        "default_stage_id":    campaign.default_stage_id,
    }


def serialize_lead(lead):
    return {
        "id":           lead.id,
        "company_id":   lead.company_id,
        "campaign_id":  lead.campaign_id,
        "name":         lead.name,
        "email":        lead.email,
        "company_name": lead.company_name,
        "job_title":    lead.job_title,
        "city":         getattr(lead, "city", None),
        "state":        getattr(lead, "state", None),
        "numero_1":     lead.numero_1,
        "numero_2":     lead.numero_2,
        "numero_3":     lead.numero_3,
        "numero_4":     lead.numero_4,
        "numero_5":     lead.numero_5,
        "numero_6":     lead.numero_6,
        "numero_7":     lead.numero_7,
        "numero_8":     lead.numero_8,
        "phones":       lead.get_all_phones(),
        "status":       lead.status,
        "notes":        lead.notes,
        "created_at":   lead.created_at.isoformat() if lead.created_at else None,
        "updated_at":   lead.updated_at.isoformat() if lead.updated_at else None,
    }


def serialize_call_basic(call):
    return {
        "id":               call.id,
        "campaign_id":      call.campaign_id,
        "lead_id":          call.lead_id,
        "lead_name":        call.lead.name if getattr(call, "lead", None) else None,
        "phone_dialed":     call.phone_dialed,
        "call_sid":         call.call_sid,
        "status":           call.status,
        "direction":        call.direction,
        "attempt":          call.attempt,
        "duration_seconds": call.duration_seconds,
        "created_at":       call.created_at.isoformat() if call.created_at else None,
        "answered_at":      call.answered_at.isoformat() if call.answered_at else None,
        "ended_at":         call.ended_at.isoformat() if call.ended_at else None,
    }


def _get_active_campaign_call(campaign_id):
    return (
        Call.query
        .filter(
            Call.campaign_id == campaign_id,
            Call.company_id  == g.company_id,
            Call.status.in_(["queued", "initiated", "ringing", "in_progress", "answered"]),
        )
        .order_by(Call.created_at.desc(), Call.id.desc())
        .first()
    )


def _get_next_campaign_lead(campaign_id):
    return (
        Lead.query
        .filter(
            Lead.campaign_id == campaign_id,
            Lead.company_id  == g.company_id,
            Lead.status      == "new",
        )
        .order_by(Lead.id.asc())
        .first()
    )


# ─────────────────────────────────────────────
# ROTA PÚBLICA (sem auth)
# ─────────────────────────────────────────────

@leads_bp.route("/ping", methods=["GET"])
def ping():
    return jsonify({"message": "pong"}), 200


# ─────────────────────────────────────────────
# CAMPANHAS
# ─────────────────────────────────────────────

@leads_bp.route("/campaign", methods=["POST"])
@require_auth
@require_role("admin", "agent")   # admin e agent podem criar campanhas
def create_campaign():
    data = request.get_json() or {}

    if not data.get("name"):
        return jsonify({"error": "name é obrigatório"}), 400

    campaign = Campaign(
        company_id          = g.company_id,   # vem do JWT, ignora body
        name                = data["name"],
        description         = data.get("description"),
        status              = data.get("status", "draft"),
        dial_mode           = data.get("dial_mode", "manual"),
        retry_limit         = int(data.get("retry_limit", 3)),
        default_pipeline_id = data.get("default_pipeline_id"),
        default_stage_id    = data.get("default_stage_id"),
        mobile_only         = bool(data.get("mobile_only", False)),
    )

    db.session.add(campaign)
    db.session.commit()

    return jsonify({
        "message":  "Campanha criada com sucesso",
        "campaign": serialize_campaign(campaign),
    }), 201


@leads_bp.route("/campaigns", methods=["GET"])
@require_auth
def list_campaigns():
    # Sempre filtra pelo tenant do usuário logado — sem query param company_id
    campaigns = (
        Campaign.query
        .filter_by(company_id=g.company_id)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    return jsonify([serialize_campaign(c) for c in campaigns]), 200


@leads_bp.route("/campaign/<int:campaign_id>", methods=["GET"])
@require_auth
def get_campaign(campaign_id):
    # filter_by com company_id garante que só o dono vê a campanha
    campaign = Campaign.query.filter_by(
        id=campaign_id, company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    return jsonify(serialize_campaign(campaign)), 200


@leads_bp.route("/campaign/<int:campaign_id>", methods=["PATCH"])
@require_auth
@require_role("admin", "agent")
def update_campaign(campaign_id):
    campaign = Campaign.query.filter_by(
        id=campaign_id, company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    data = request.get_json() or {}
    
    if "name" in data:
        name = data["name"].strip()
        if not name:
            return jsonify({"error": "Nome não pode ser vazio"}), 400
        campaign.name = name
    
    if "description" in data:
        campaign.description = data["description"]
    
    if "status" in data:
        campaign.status = data["status"]

    db.session.commit()

    return jsonify({
        "message": "Campanha atualizada com sucesso",
        "campaign": serialize_campaign(campaign)
    }), 200


@leads_bp.route("/campaign/<int:campaign_id>/start", methods=["POST"])
@require_auth
@require_role("admin", "agent")
def start_campaign(campaign_id):
    campaign = Campaign.query.filter_by(
        id=campaign_id, company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    campaign.status = "running"
    db.session.commit()

    return jsonify({
        "message":  "Campanha iniciada com sucesso",
        "campaign": serialize_campaign(campaign),
    }), 200


@leads_bp.route("/campaign/<int:campaign_id>/pause", methods=["POST"])
@require_auth
@require_role("admin", "agent")
def pause_campaign(campaign_id):
    campaign = Campaign.query.filter_by(
        id=campaign_id, company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    campaign.status = "paused"
    db.session.commit()

    return jsonify({
        "message":  "Campanha pausada com sucesso",
        "campaign": serialize_campaign(campaign),
    }), 200


@leads_bp.route("/campaign/<int:campaign_id>/progress", methods=["GET"])
@require_auth
def campaign_progress(campaign_id):
    campaign = Campaign.query.filter_by(
        id=campaign_id, company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    def lead_count(status):
        return Lead.query.filter(
            Lead.campaign_id == campaign_id,
            Lead.company_id  == g.company_id,
            Lead.status      == status,
        ).count()

    total_leads     = Lead.query.filter_by(campaign_id=campaign_id, company_id=g.company_id).count()
    new_leads       = lead_count("new")
    dialing_leads   = lead_count("dialing")
    contacted_leads = lead_count("contacted")
    invalid_leads   = lead_count("invalid")
    processed_leads = total_leads - new_leads

    def call_count(*statuses):
        return Call.query.filter(
            Call.campaign_id == campaign_id,
            Call.company_id  == g.company_id,
            Call.status.in_(statuses),
        ).count()

    total_calls    = Call.query.filter_by(campaign_id=campaign_id, company_id=g.company_id).count()
    answered_calls = call_count("completed", "answered", "in_progress")
    failed_calls   = call_count("failed", "busy", "no_answer", "canceled")

    duration_total = (
        db.session.query(func.coalesce(func.sum(Call.duration_seconds), 0))
        .filter(Call.campaign_id == campaign_id, Call.company_id == g.company_id)
        .scalar()
    ) or 0

    current_lead = (
        Lead.query
        .filter(Lead.campaign_id == campaign_id, Lead.company_id == g.company_id,
                Lead.status == "dialing")
        .order_by(Lead.updated_at.desc(), Lead.id.desc())
        .first()
    )
    latest_call = (
        Call.query
        .filter(Call.campaign_id == campaign_id, Call.company_id == g.company_id)
        .order_by(Call.created_at.desc(), Call.id.desc())
        .first()
    )

    # Leads detalhados com última chamada — para tabela de progresso
    leads_page = request.args.get("page", 1, type=int)
    leads_per_page = 50
    leads_offset   = (leads_page - 1) * leads_per_page

    all_leads = (
        Lead.query
        .filter(Lead.campaign_id == campaign_id, Lead.company_id == g.company_id)
        .order_by(Lead.id.asc())
        .limit(leads_per_page)
        .offset(leads_offset)
        .all()
    )

    def lead_with_last_call(lead):
        last_call = (
            Call.query
            .filter(Call.lead_id == lead.id, Call.company_id == g.company_id)
            .order_by(Call.created_at.desc())
            .first()
        )
        return {
            **serialize_lead(lead),
            "last_call_status": last_call.status if last_call else None,
            "last_call_at":     last_call.created_at.isoformat() if last_call and last_call.created_at else None,
        }

    return jsonify({
        "campaign": serialize_campaign(campaign),
        "summary": {
            "total_leads":            total_leads,
            "processed_leads":        processed_leads,
            "pending_leads":          new_leads,
            "dialing_leads":          dialing_leads,
            "contacted_leads":        contacted_leads,
            "invalid_leads":          invalid_leads,
            "total_calls":            total_calls,
            "answered_calls":         answered_calls,
            "failed_calls":           failed_calls,
            "total_duration_seconds": duration_total,
            "progress_percent":       round((processed_leads / total_leads) * 100, 2) if total_leads else 0,
        },
        "current_lead": serialize_lead(current_lead) if current_lead else None,
        "latest_call":  serialize_call_basic(latest_call) if latest_call else None,
        "leads":        [lead_with_last_call(l) for l in all_leads],
        "leads_page":   leads_page,
    }), 200


@leads_bp.route("/campaign/<int:campaign_id>/dial-next", methods=["POST"])
@require_auth
def dial_next_lead(campaign_id):
    campaign = Campaign.query.filter_by(
        id=campaign_id, company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    if campaign.status != "running":
        return jsonify({"error": "A campanha precisa estar com status running"}), 400

    active_call = _get_active_campaign_call(campaign_id)
    if active_call:
        return jsonify({
            "error":       "Já existe uma chamada em andamento nesta campanha",
            "active_call": serialize_call_basic(active_call),
        }), 400

    lead = _get_next_campaign_lead(campaign_id)
    if not lead:
        campaign.status = "finished"
        db.session.commit()
        return jsonify({
            "message":  "Nenhum lead pendente. Campanha finalizada.",
            "campaign": serialize_campaign(campaign),
        }), 200

    phone_to_call = lead.get_primary_phone()
    if not phone_to_call:
        lead.status = "invalid"
        db.session.commit()
        return jsonify({"error": "Lead sem número principal"}), 400

    phone_to_call = normalize_phone_br(phone_to_call)

    try:
        company = Company.query.get(g.company_id)
        service = TwilioService.from_company(company)
        status_callback_url = request.host_url.rstrip("/") + "/api/twilio/status"

        last_attempt = (
            db.session.query(func.max(Call.attempt))
            .filter(Call.lead_id == lead.id, Call.company_id == g.company_id)
            .scalar()
        ) or 0

        call_sid = service.make_call(
            to_number=phone_to_call,
            status_callback_url=status_callback_url,
        )

        call = Call(
            company_id   = g.company_id,
            campaign_id  = lead.campaign_id,
            lead_id      = lead.id,
            phone_dialed = phone_to_call,
            call_sid     = call_sid,
            status       = "queued",
            direction    = "outbound",
            attempt      = last_attempt + 1,
        )

        db.session.add(call)
        lead.status = "dialing"
        db.session.commit()

        return jsonify({
            "message":  "Próxima ligação iniciada com sucesso",
            "campaign": serialize_campaign(campaign),
            "lead":     serialize_lead(lead),
            "call":     serialize_call_basic(call),
        }), 200

    except InsufficientCreditError as e:
        db.session.rollback()
        return jsonify({"error": "Saldo insuficiente. Recarregue seu crédito.", "balance": e.balance}), 402
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@leads_bp.route("/campaign/<int:campaign_id>/tick", methods=["POST"])
@require_auth
def tick_campaign(campaign_id):
    campaign = Campaign.query.filter_by(
        id=campaign_id, company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    if campaign.status != "running":
        return jsonify({
            "message":  "Campanha não está em execução",
            "campaign": serialize_campaign(campaign),
        }), 200

    active_call = _get_active_campaign_call(campaign_id)
    if active_call:
        return jsonify({
            "message":     "Campanha aguardando conclusão da chamada ativa",
            "campaign":    serialize_campaign(campaign),
            "active_call": serialize_call_basic(active_call),
        }), 200

    next_lead = _get_next_campaign_lead(campaign_id)
    if not next_lead:
        campaign.status = "finished"
        db.session.commit()
        return jsonify({
            "message":  "Campanha finalizada automaticamente",
            "campaign": serialize_campaign(campaign),
        }), 200

    phone_to_call = next_lead.get_primary_phone()
    if not phone_to_call:
        next_lead.status = "invalid"
        db.session.commit()
        return jsonify({
            "message": "Lead sem número principal, marcado como inválido",
            "lead":    serialize_lead(next_lead),
        }), 200

    phone_to_call = normalize_phone_br(phone_to_call)

    try:
        company = Company.query.get(g.company_id)
        service = TwilioService.from_company(company)
        status_callback_url = request.host_url.rstrip("/") + "/api/twilio/status"

        last_attempt = (
            db.session.query(func.max(Call.attempt))
            .filter(Call.lead_id == next_lead.id, Call.company_id == g.company_id)
            .scalar()
        ) or 0

        call_sid = service.make_call(
            to_number=phone_to_call,
            status_callback_url=status_callback_url,
        )

        call = Call(
            company_id   = g.company_id,
            campaign_id  = next_lead.campaign_id,
            lead_id      = next_lead.id,
            phone_dialed = phone_to_call,
            call_sid     = call_sid,
            status       = "queued",
            direction    = "outbound",
            attempt      = last_attempt + 1,
        )

        db.session.add(call)
        next_lead.status = "dialing"
        db.session.commit()

        return jsonify({
            "message":  "Tick executado e próxima ligação iniciada",
            "campaign": serialize_campaign(campaign),
            "lead":     serialize_lead(next_lead),
            "call":     serialize_call_basic(call),
        }), 200

    except InsufficientCreditError as e:
        db.session.rollback()
        return jsonify({"error": "Saldo insuficiente. Recarregue seu crédito.", "balance": e.balance}), 402
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# LEADS
# ─────────────────────────────────────────────

@leads_bp.route("/lead", methods=["POST"])
@require_auth
def create_lead():
    data = request.get_json() or {}

    if not data.get("campaign_id"):
        return jsonify({"error": "campaign_id é obrigatório"}), 400
    if not data.get("name"):
        return jsonify({"error": "name é obrigatório"}), 400
    if not data.get("numero_1"):
        return jsonify({"error": "numero_1 é obrigatório"}), 400

    # Verifica que a campanha pertence ao tenant antes de criar o lead
    campaign = Campaign.query.filter_by(
        id=data["campaign_id"], company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    lead = Lead(
        company_id  = g.company_id,
        campaign_id = data["campaign_id"],
        name        = data["name"],
        email       = data.get("email"),
        company_name= data.get("company_name"),
        job_title   = data.get("job_title"),
        numero_1    = data.get("numero_1"),
        numero_2    = data.get("numero_2"),
        numero_3    = data.get("numero_3"),
        numero_4    = data.get("numero_4"),
        numero_5    = data.get("numero_5"),
        numero_6    = data.get("numero_6"),
        numero_7    = data.get("numero_7"),
        numero_8    = data.get("numero_8"),
        status      = data.get("status", "new"),
        notes       = data.get("notes"),
    )

    db.session.add(lead)
    db.session.flush()  # garante lead.id para o Deal

    # Criar Deal automático na pipeline da campanha (ou pipeline padrão)
    try:
        pipeline_id = data.get("pipeline_id") or getattr(campaign, "default_pipeline_id", None)
        stage_id    = data.get("stage_id")    or getattr(campaign, "default_stage_id", None)

        target_pipeline = None
        first_stage = None

        if pipeline_id:
            target_pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=g.company_id).first()
        if not target_pipeline:
            target_pipeline = Pipeline.query.filter_by(company_id=g.company_id, is_default=True).first()
        if not target_pipeline:
            target_pipeline = Pipeline.query.filter_by(company_id=g.company_id).first()

        if target_pipeline:
            if stage_id:
                first_stage = PipelineStage.query.filter_by(id=stage_id, pipeline_id=target_pipeline.id).first()
            if not first_stage and target_pipeline.stages:
                first_stage = target_pipeline.stages[0]

        if target_pipeline and first_stage:
            from app.models.deal import Deal
            deal = Deal(
                company_id  = g.company_id,
                pipeline_id = target_pipeline.id,
                stage_id    = first_stage.id,
                lead_id     = lead.id,
                title       = lead.name,
                status      = "open",
            )
            db.session.add(deal)
    except Exception:
        pass  # nunca travar criação de lead por erro de CRM

    db.session.commit()

    return jsonify({
        "message": "Lead criado com sucesso",
        "lead":    serialize_lead(lead),
    }), 201


@leads_bp.route("/leads", methods=["GET"])
@require_auth
def list_leads():
    campaign_id = request.args.get("campaign_id", type=int)
    status      = request.args.get("status")
    page        = request.args.get("page", 1, type=int)
    per_page    = request.args.get("per_page", 20, type=int)

    query = Lead.query.filter(Lead.company_id == g.company_id)

    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)
    if status:
        query = query.filter(Lead.status == status)

    # Paginação
    pagination = query.order_by(Lead.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "leads": [serialize_lead(l) for l in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page,
        "per_page": per_page
    }), 200


@leads_bp.route("/lead/<int:lead_id>", methods=["GET"])
@require_auth
def get_lead(lead_id):
    lead = Lead.query.filter_by(id=lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    return jsonify(serialize_lead(lead)), 200


@leads_bp.route("/leads-pending", methods=["GET"])
@require_auth
def list_pending_leads():
    campaign_id = request.args.get("campaign_id", type=int)

    query = Lead.query.filter(
        Lead.company_id == g.company_id,
        Lead.status     == "new",
    )
    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)

    leads = query.order_by(Lead.import_order.asc(), Lead.id.asc()).all()
    return jsonify([serialize_lead(l) for l in leads]), 200


@leads_bp.route("/leads/import", methods=["POST"])
@require_auth
@require_role("admin", "agent")
def import_leads():
    """
    Importa leads de CSV ou XLSX.

    Colunas aceitas (inglês ou português):
      name / nome, numero_1, numero_2…numero_8,
      email, company_name / empresa, job_title / cargo,
      city / cidade, state / estado, notes / observacoes

    Ao importar cada lead com sucesso, cria automaticamente um Deal
    no pipeline padrão da empresa (estágio "Novo").
    """
    file        = request.files.get("file")
    campaign_id = request.form.get("campaign_id", type=int)

    if not file:
        return jsonify({"error": "Arquivo não enviado"}), 400
    if not campaign_id:
        return jsonify({"error": "campaign_id é obrigatório"}), 400

    # Verifica que a campanha pertence ao tenant
    campaign = Campaign.query.filter_by(
        id=campaign_id, company_id=g.company_id
    ).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        return jsonify({"error": f"Erro ao ler arquivo: {str(e)}"}), 400

    # Normaliza nomes de colunas — suporta PT-BR e EN
    col_map = {
        "nome":         "name",
        "empresa":      "company_name",
        "cargo":        "job_title",
        "cidade":       "city",
        "estado":       "state",
        "observacoes":  "notes",
        "observações":  "notes",
    }
    df.rename(columns=col_map, inplace=True)
    df.columns = [c.strip().lower() for c in df.columns]

    pipeline_id = request.form.get("pipeline_id", type=int)
    stage_id = request.form.get("stage_id", type=int)

    # Resolve Pipeline e Stage: Form -> Campaign -> Default Company
    target_pipeline_id = pipeline_id or getattr(campaign, "default_pipeline_id", None)
    target_stage_id = stage_id or getattr(campaign, "default_stage_id", None)
    
    pipeline = None
    first_stage = None

    if target_pipeline_id:
        pipeline = Pipeline.query.filter_by(id=target_pipeline_id, company_id=g.company_id).first()
    
    if not pipeline:
        pipeline = Pipeline.query.filter_by(company_id=g.company_id, is_default=True).first()
        
    if pipeline:
        if target_stage_id:
            first_stage = PipelineStage.query.filter_by(id=target_stage_id, pipeline_id=pipeline.id).first()
        if not first_stage and pipeline.stages:
            first_stage = pipeline.stages[0]

    def _safe(val):
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        
        # Se for número (float ou int), converte para int se não tiver casas decimais significativas
        # Isso evita que "11999999999" vire "11999999999.0"
        if isinstance(val, (float, int)):
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            return str(val)

        res = str(val).strip()
        return res if res else None

    imported = 0
    skipped  = 0
    errors   = []

    # Obter próxima ordem de importação para esta campanha
    last_order = (
        db.session.query(db.func.max(Lead.import_order))
        .filter(Lead.campaign_id == campaign_id)
        .scalar()
    ) or 0

    for index, row in df.iterrows():
        name     = _safe(row.get("name"))
        numero_1 = _safe(row.get("numero_1"))

        if not name:
            errors.append(f"Linha {index + 2}: 'name' / 'nome' é obrigatório")
            skipped += 1
            continue

        if not numero_1:
            errors.append(f"Linha {index + 2}: 'numero_1' é obrigatório")
            skipped += 1
            continue

        last_order += 1
        lead = Lead(
            company_id   = g.company_id,
            campaign_id  = campaign_id,
            name         = name,
            email        = _safe(row.get("email")),
            company_name = _safe(row.get("company_name")),
            job_title    = _safe(row.get("job_title")),
            city         = _safe(row.get("city")),
            state        = _safe(row.get("state")),
            notes        = _safe(row.get("notes")),
            numero_1     = numero_1,
            numero_2     = _safe(row.get("numero_2")),
            numero_3     = _safe(row.get("numero_3")),
            numero_4     = _safe(row.get("numero_4")),
            numero_5     = _safe(row.get("numero_5")),
            numero_6     = _safe(row.get("numero_6")),
            numero_7     = _safe(row.get("numero_7")),
            numero_8     = _safe(row.get("numero_8")),
            status       = "new",
            import_order = last_order,
        )
        db.session.add(lead)
        db.session.flush()  # garante lead.id para o Deal

        # Criar Deal automático no pipeline configurado
        if pipeline and first_stage:
            deal = Deal(
                company_id   = g.company_id,
                pipeline_id  = pipeline.id,
                stage_id     = first_stage.id,
                lead_id      = lead.id,
                title        = lead.name,
                status       = "open",
            )
            db.session.add(deal)

        imported += 1

    db.session.commit()

    resp = {
        "message":      "Importação concluída",
        "imported":     imported,
        "skipped":      skipped,
        "errors_count": len(errors),
        "errors":       errors[:20],
        "crm_pipeline": pipeline.name if pipeline else None,
        "crm_stage":    first_stage.name if first_stage else None,
    }
    return jsonify(resp), 200


@leads_bp.route("/campaign/<int:campaign_id>", methods=["DELETE"])
@require_auth
@require_role("admin", "agent")
def delete_campaign(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    # Stop any running auto-dialer session
    try:
        from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS
        session = AUTO_DIALER_SESSIONS.get(campaign_id)
        if session:
            session["status"] = "stopped"
            del AUTO_DIALER_SESSIONS[campaign_id]
    except Exception:
        pass

    db.session.delete(campaign)
    db.session.commit()
    return jsonify({"message": "Campanha excluída com sucesso"}), 200


@leads_bp.route("/campaign/<int:campaign_id>/reset-leads", methods=["POST"])
@require_auth
@require_role("admin", "agent")
def reset_campaign_leads(campaign_id):
    """Reset all leads in a campaign back to 'new' status."""
    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    Lead.query.filter_by(
        campaign_id=campaign_id, company_id=g.company_id
    ).update({"status": "new"})
    
    # Marca as chamadas antigas como 'reset' para que o _phones_tried ignore elas,
    # permitindo que o discador disque todos os números novamente, mas sem deletar do histórico.
    from app.models.call import Call
    Call.query.filter_by(
        campaign_id=campaign_id, company_id=g.company_id
    ).update({"status": "reset"})
    # Se houver uma sessão de discador ativa para esta campanha, precisamos resetá-la
    try:
        from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS
        session = AUTO_DIALER_SESSIONS.get(campaign_id)
        if session:
            session["leads_done"] = 0
            session["current_lead_id"] = None
            session["current_lead_name"] = None
            session["status"] = "paused" # Reset normalmente para o estado pausado
            
            # Recalcula pendentes para o UI
            pending = Lead.query.filter(
                Lead.campaign_id == campaign_id,
                Lead.company_id  == g.company_id,
                Lead.status.in_(["new", "novo"]),
            ).count()
            session["leads_pending"] = pending
            logger.info("[RESET] Memória do discador sincronizada para campaign=%s", campaign_id)
    except Exception as e:
        logger.error("[RESET] Erro ao sincronizar memória do discador: %s", e)

    db.session.commit()
    return jsonify({"message": "Campanha resetada com sucesso. Todos os leads voltaram para 'novo'."}), 200


@leads_bp.route("/campaign/<int:campaign_id>/clear-leads", methods=["POST", "DELETE"])
@require_auth
@require_role("admin", "agent")
def clear_campaign_leads(campaign_id):
    """Delete all leads associated with a campaign without deleting the campaign itself."""
    campaign = Campaign.query.filter_by(id=campaign_id, company_id=g.company_id).first()
    if not campaign:
        return jsonify({"error": "Campanha não encontrada"}), 404

    # Stop any running auto-dialer session
    try:
        from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS
        session = AUTO_DIALER_SESSIONS.get(campaign_id)
        if session:
            session["status"] = "stopped"
            del AUTO_DIALER_SESSIONS[campaign_id]
    except Exception:
        pass

    Lead.query.filter_by(campaign_id=campaign_id, company_id=g.company_id).delete()
    db.session.commit()
    return jsonify({"message": "Todos os leads da campanha foram excluídos."}), 200


@leads_bp.route("/clear-all-leads", methods=["POST", "DELETE"])
@require_auth
@require_role("admin")
def clear_all_leads():
    """Delete all leads and their deals from the user's company."""
    try:
        from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS
        for c_id, sess in list(AUTO_DIALER_SESSIONS.items()):
            if sess.get("company_id") == g.company_id:
                sess["status"] = "stopped"
                del AUTO_DIALER_SESSIONS[c_id]
    except Exception:
        pass

    # Delete deals first (they depend on lead_id)
    try:
        from app.models.deal import Deal
        Deal.query.filter_by(company_id=g.company_id).delete()
    except Exception:
        pass

    Lead.query.filter_by(company_id=g.company_id).delete()
    db.session.commit()
    return jsonify({"message": "Todos os leads e deals foram excluídos."}), 200
