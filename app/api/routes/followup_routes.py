"""
Follow-Up Sequences API
=======================
Blueprint : followup_bp
Prefix    : /api/followup

Endpoints
---------
GET    /api/followup/sequences              List sequences (filtered by campaign_id if given)
POST   /api/followup/sequences              Create sequence
PUT    /api/followup/sequences/<id>         Update sequence
DELETE /api/followup/sequences/<id>         Delete sequence

GET    /api/followup/tasks                  Pending tasks (ready to send)
POST   /api/followup/tasks/<id>/mark-sent   Mark task as sent
POST   /api/followup/tasks/<id>/skip        Skip task
"""
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.auth import require_auth, require_role
from app.extensions import db
from app.models.followup import FollowUpSequence, FollowUpTask

followup_bp = Blueprint("followup", __name__, url_prefix="/api/followup")


def _seq_to_dict(s: FollowUpSequence) -> dict:
    return {
        "id":                   s.id,
        "company_id":           s.company_id,
        "campaign_id":          s.campaign_id,
        "name":                 s.name,
        "trigger_disposition":  s.trigger_disposition,
        "is_active":            s.is_active,
        "steps":                s.steps or [],
        "created_at":           s.created_at.isoformat() if s.created_at else None,
    }


def _task_to_dict(t: FollowUpTask) -> dict:
    lead = t.lead
    return {
        "id":           t.id,
        "sequence_id":  t.sequence_id,
        "sequence_name": t.sequence.name if t.sequence else None,
        "lead_id":      t.lead_id,
        "lead_name":    lead.name if lead else None,
        "lead_phone":   lead.numero_1 if lead else None,
        "call_id":      t.call_id,
        "step_index":   t.step_index,
        "action":       t.action,
        "template":     t.template,
        "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
        "status":       t.status,
        "executed_at":  t.executed_at.isoformat() if t.executed_at else None,
        "error":        t.error,
        "created_at":   t.created_at.isoformat() if t.created_at else None,
    }


# ── Sequences ──────────────────────────────────────────────────────────────

@followup_bp.route("/sequences", methods=["GET"])
@require_auth
def list_sequences():
    campaign_id = request.args.get("campaign_id", type=int)
    q = FollowUpSequence.query.filter_by(company_id=g.company_id)
    if campaign_id:
        q = q.filter_by(campaign_id=campaign_id)
    return jsonify([_seq_to_dict(s) for s in q.order_by(FollowUpSequence.created_at.desc()).all()])


@followup_bp.route("/sequences", methods=["POST"])
@require_auth
@require_role("admin")
def create_sequence():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    trigger = (data.get("trigger_disposition") or "").strip()
    if not name or not trigger:
        return jsonify({"error": "name e trigger_disposition são obrigatórios"}), 400

    steps = data.get("steps") or []
    if not isinstance(steps, list):
        return jsonify({"error": "steps deve ser uma lista"}), 400

    seq = FollowUpSequence(
        company_id=g.company_id,
        campaign_id=data.get("campaign_id"),
        name=name,
        trigger_disposition=trigger,
        is_active=bool(data.get("is_active", True)),
        steps=steps,
    )
    db.session.add(seq)
    db.session.commit()
    return jsonify(_seq_to_dict(seq)), 201


@followup_bp.route("/sequences/<int:seq_id>", methods=["PUT"])
@require_auth
@require_role("admin")
def update_sequence(seq_id: int):
    seq = FollowUpSequence.query.filter_by(id=seq_id, company_id=g.company_id).first()
    if not seq:
        return jsonify({"error": "Sequência não encontrada"}), 404

    data = request.get_json() or {}
    if "name" in data:
        seq.name = data["name"].strip() or seq.name
    if "trigger_disposition" in data:
        seq.trigger_disposition = data["trigger_disposition"].strip() or seq.trigger_disposition
    if "is_active" in data:
        seq.is_active = bool(data["is_active"])
    if "campaign_id" in data:
        seq.campaign_id = data["campaign_id"]
    if "steps" in data and isinstance(data["steps"], list):
        seq.steps = data["steps"]

    db.session.commit()
    return jsonify(_seq_to_dict(seq))


@followup_bp.route("/sequences/<int:seq_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_sequence(seq_id: int):
    seq = FollowUpSequence.query.filter_by(id=seq_id, company_id=g.company_id).first()
    if not seq:
        return jsonify({"error": "Sequência não encontrada"}), 404
    db.session.delete(seq)
    db.session.commit()
    return jsonify({"ok": True})


# ── Tasks ──────────────────────────────────────────────────────────────────

@followup_bp.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    status = request.args.get("status", "pending")
    page   = request.args.get("page", 1, type=int)
    limit  = request.args.get("per_page", 25, type=int)

    q = FollowUpTask.query.filter_by(company_id=g.company_id)
    if status:
        q = q.filter_by(status=status)
    # Only show tasks ready or overdue
    if status == "pending":
        q = q.filter(FollowUpTask.scheduled_at <= datetime.utcnow())
    q = q.order_by(FollowUpTask.scheduled_at.asc())

    total = q.count()
    tasks = q.offset((page - 1) * limit).limit(limit).all()

    return jsonify({
        "tasks":   [_task_to_dict(t) for t in tasks],
        "total":   total,
        "page":    page,
        "per_page": limit,
    })


@followup_bp.route("/tasks/<int:task_id>/mark-sent", methods=["POST"])
@require_auth
def mark_task_sent(task_id: int):
    task = FollowUpTask.query.filter_by(id=task_id, company_id=g.company_id).first()
    if not task:
        return jsonify({"error": "Tarefa não encontrada"}), 404
    task.status      = "sent"
    task.executed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


@followup_bp.route("/tasks/<int:task_id>/skip", methods=["POST"])
@require_auth
def skip_task(task_id: int):
    task = FollowUpTask.query.filter_by(id=task_id, company_id=g.company_id).first()
    if not task:
        return jsonify({"error": "Tarefa não encontrada"}), 404
    task.status      = "skipped"
    task.executed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


# ── Internal enrollment helper ─────────────────────────────────────────────

def enroll_lead_in_followup(company_id: int, lead_id: int, campaign_id: int,
                             call_id: int, disposition: str):
    """
    Called after a call ends. Finds active sequences matching the disposition
    and creates FollowUpTask rows for each step.
    """
    try:
        from datetime import timedelta
        seqs = FollowUpSequence.query.filter_by(
            company_id=company_id,
            trigger_disposition=disposition,
            is_active=True,
        ).filter(
            (FollowUpSequence.campaign_id == campaign_id) |
            (FollowUpSequence.campaign_id.is_(None))
        ).all()

        for seq in seqs:
            for idx, step in enumerate(seq.steps or []):
                delay = int(step.get("delay_minutes") or 0)
                action = step.get("action") or "email"
                template = step.get("template") or ""
                scheduled = datetime.utcnow() + timedelta(minutes=delay)
                task = FollowUpTask(
                    company_id=company_id,
                    sequence_id=seq.id,
                    lead_id=lead_id,
                    call_id=call_id,
                    step_index=idx,
                    action=action,
                    template=template,
                    scheduled_at=scheduled,
                    status="pending",
                )
                db.session.add(task)
        db.session.commit()
    except Exception:
        db.session.rollback()
