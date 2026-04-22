import csv
import io

from flask import Blueprint, jsonify, request, Response

from app.auth import require_auth
from app.extensions import db
from app.models.lead import Lead

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