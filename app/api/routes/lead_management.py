import csv
import io

from flask import Blueprint, jsonify, request, Response

from app.auth import require_auth
from app.extensions import db
from app.models.lead import Lead
from app.models.call import Call

lead_management_bp = Blueprint(
    "lead_management",
    __name__,
    url_prefix="/api/leads"
)


def _lead_to_dict(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "name": getattr(lead, "name", None),
        "email": getattr(lead, "email", None),
        "company_name": getattr(lead, "company_name", None),
        "job_title": getattr(lead, "job_title", None),
        "notes": getattr(lead, "notes", None),
        "status": getattr(lead, "status", None),
        "numero_1": getattr(lead, "numero_1", None),
        "numero_2": getattr(lead, "numero_2", None),
        "numero_3": getattr(lead, "numero_3", None),
        "numero_4": getattr(lead, "numero_4", None),
        "numero_5": getattr(lead, "numero_5", None),
        "numero_6": getattr(lead, "numero_6", None),
        "numero_7": getattr(lead, "numero_7", None),
        "numero_8": getattr(lead, "numero_8", None),
    }


@lead_management_bp.route("/<int:lead_id>", methods=["GET"])
def get_lead(lead_id: int):
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({"error": "lead não encontrado"}), 404

    return jsonify({"lead": _lead_to_dict(lead)}), 200


@lead_management_bp.route("/<int:lead_id>", methods=["PUT"])
def update_lead(lead_id: int):
    data = request.get_json(silent=True) or {}

    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({"error": "lead não encontrado"}), 404

    allowed_fields = [
        "name",
        "email",
        "company_name",
        "job_title",
        "notes",
        "status",
        "numero_1",
        "numero_2",
        "numero_3",
        "numero_4",
        "numero_5",
        "numero_6",
        "numero_7",
        "numero_8",
    ]

    try:
        for field in allowed_fields:
            if field in data:
                setattr(lead, field, data.get(field))

        db.session.commit()

        return jsonify({
            "message": "lead atualizado com sucesso",
            "lead": _lead_to_dict(lead)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@lead_management_bp.route("/export", methods=["GET"])
@require_auth
def export_leads():
    """
    Exporta leads em CSV filtrado por campanha e/ou status.
    Query params:
      campaign_id – opcional; se omitido exporta todos da empresa
      status      – opcional, pode repetir: ?status=voicemail&status=no_answer
    """
    from flask import g
    campaign_id = request.args.get("campaign_id", type=int)
    statuses = request.args.getlist("status")

    query = Lead.query.filter(Lead.company_id == g.company_id)

    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)

    if statuses:
        query = query.filter(Lead.status.in_(statuses))

    leads = query.order_by(Lead.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Campanha ID", "Nome", "Email", "Empresa", "Cargo", "Cidade", "Estado",
        "Status", "Numero 1", "Numero 2", "Numero 3", "Numero 4",
        "Numero 5", "Numero 6", "Numero 7", "Numero 8", "Observações"
    ])
    for lead in leads:
        writer.writerow([
            lead.id, lead.campaign_id, lead.name, lead.email or "",
            lead.company_name or "", lead.job_title or "", lead.city or "", lead.state or "",
            lead.status or "", lead.numero_1 or "", lead.numero_2 or "",
            lead.numero_3 or "", lead.numero_4 or "", lead.numero_5 or "",
            lead.numero_6 or "", lead.numero_7 or "", lead.numero_8 or "",
            lead.notes or "",
        ])

    output.seek(0)
    status_label = "_".join(statuses) if statuses else "todos"
    if campaign_id:
        filename = f"leads_campanha_{campaign_id}_{status_label}.csv"
    else:
        filename = f"leads_sistema_{status_label}.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@lead_management_bp.route("/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id: int):
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({"error": "lead não encontrado"}), 404

    try:
        db.session.delete(lead)
        db.session.commit()

        return jsonify({
            "message": "lead removido com sucesso",
            "lead_id": lead_id
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@lead_management_bp.route("/<int:lead_id>/call-history", methods=["GET"])
@require_auth
def lead_call_history(lead_id: int):
    """Retorna as últimas 3 tentativas de chamada para um lead."""
    from flask import g
    lead = Lead.query.filter_by(id=lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    calls = (
        Call.query
        .filter_by(lead_id=lead_id)
        .order_by(Call.created_at.desc())
        .limit(3)
        .all()
    )

    history = []
    for c in calls:
        history.append({
            "id":         c.id,
            "status":     c.status,
            "direction":  c.direction,
            "duration":   c.duration_seconds,
            "amd_result": getattr(c, "amd_result", None),
            "notes":      getattr(c, "notes", None),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return jsonify({
        "lead_id":       lead_id,
        "lead_status":   lead.status,
        "notes":         lead.notes,
        "calls":         history,
    })


@lead_management_bp.route("/<int:lead_id>/activity", methods=["GET"])
@require_auth
def lead_activity_timeline(lead_id: int):
    """Retorna timeline unificada de atividades do lead (chamadas + notas + CRM)."""
    from flask import g
    from app.models.deal import Deal
    from app.models.deal_activity import DealActivity

    lead = Lead.query.filter_by(id=lead_id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"error": "Lead não encontrado"}), 404

    events = []

    # Lead criado
    events.append({
        "type":       "lead_created",
        "title":      "Lead adicionado",
        "body":       None,
        "icon":       "person_add",
        "color":      "#6366f1",
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
    })

    # Notas do lead
    if lead.notes and lead.notes.strip():
        events.append({
            "type":       "note",
            "title":      "Nota",
            "body":       lead.notes.strip(),
            "icon":       "note",
            "color":      "#f59e0b",
            "created_at": lead.updated_at.isoformat() if getattr(lead, "updated_at", None) else lead.created_at.isoformat() if lead.created_at else None,
        })

    # Chamadas
    calls = (
        Call.query
        .filter_by(lead_id=lead_id)
        .order_by(Call.created_at.asc())
        .all()
    )
    _STATUS_LABELS = {
        "completed": "Atendeu", "answered": "Atendeu",
        "voicemail": "Caixa postal", "no_answer": "Não atendeu",
        "busy": "Ocupado", "failed": "Falhou",
        "machine": "Secretária eletrônica", "in_call": "Em chamada",
    }
    _STATUS_COLORS = {
        "completed": "#22c55e", "answered": "#22c55e",
        "voicemail": "#f59e0b", "no_answer": "#6b7280",
        "busy": "#ef4444", "failed": "#ef4444",
        "machine": "#8b5cf6", "in_call": "#3b82f6",
    }
    for c in calls:
        label = _STATUS_LABELS.get(c.status, c.status or "Chamada")
        color = _STATUS_COLORS.get(c.status, "#94a3b8")
        dur = f"{c.duration_seconds}s" if c.duration_seconds else None
        body_parts = []
        if dur:
            body_parts.append(f"Duração: {dur}")
        if c.amd_result:
            amd_map = {"human": "Humano", "machine_start": "Máquina", "unknown": "Desconhecido", "timeout": "Timeout"}
            body_parts.append(f"AMD: {amd_map.get(c.amd_result, c.amd_result)}")
        if getattr(c, "notes", None):
            body_parts.append(c.notes)
        events.append({
            "type":       "call",
            "title":      label,
            "body":       " · ".join(body_parts) if body_parts else None,
            "icon":       "call",
            "color":      color,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    # Atividades CRM via Deal
    deals = Deal.query.filter_by(lead_id=lead_id, company_id=g.company_id).all()
    _ACT_ICONS = {
        "call": "call", "note": "note", "email": "email",
        "whatsapp": "chat", "meeting": "event", "stage_change": "swap_horiz",
        "pipeline_transfer": "account_tree", "system": "settings",
    }
    _ACT_COLORS = {
        "call": "#3b82f6", "note": "#f59e0b", "email": "#6366f1",
        "whatsapp": "#22c55e", "meeting": "#ec4899", "stage_change": "#8b5cf6",
        "pipeline_transfer": "#06b6d4", "system": "#94a3b8",
    }
    for deal in deals:
        for act in (deal.activities or []):
            events.append({
                "type":       act.type,
                "title":      act.title or act.type,
                "body":       act.body,
                "icon":       _ACT_ICONS.get(act.type, "circle"),
                "color":      _ACT_COLORS.get(act.type, "#94a3b8"),
                "created_at": act.created_at.isoformat() if act.created_at else None,
            })

    # Ordenar cronologicamente (mais antigo primeiro → timeline top-to-bottom)
    events.sort(key=lambda e: e["created_at"] or "")

    return jsonify({
        "lead_id":     lead_id,
        "lead_status": lead.status,
        "events":      events,
    })