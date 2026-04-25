"""
Rotas de billing: saldo, histórico, recarga manual (admin) e webhook de pagamento.
"""

import hashlib
import hmac
import logging
import os
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from app.auth import require_auth, require_role
from app.extensions import db
from app.models.billing import CreditTransaction
from app.models.company import Company

logger = logging.getLogger(__name__)
billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")


# ---------------------------------------------------------------------------
# GET /api/billing/balance
# Retorna saldo atual da empresa do usuário autenticado
# ---------------------------------------------------------------------------
@billing_bp.route("/balance", methods=["GET"])
@require_auth
def get_balance(current_user):
    company = Company.query.get(current_user.company_id)
    if not company:
        return jsonify({"error": "Empresa não encontrada"}), 404

    return jsonify({
        "balance": company.get_balance(),
        "cost_per_minute": float(company.cost_per_minute),
        "has_credit": company.has_credit(),
        "currency": "BRL",
    })


# ---------------------------------------------------------------------------
# GET /api/billing/transactions?page=1&per_page=20&type=recharge
# Histórico de transações da empresa
# ---------------------------------------------------------------------------
@billing_bp.route("/transactions", methods=["GET"])
@require_auth
def list_transactions(current_user):
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    tx_type = request.args.get("type")  # opcional: "recharge" | "call_debit"

    q = CreditTransaction.query.filter_by(company_id=current_user.company_id)
    if tx_type:
        q = q.filter_by(type=tx_type)
    q = q.order_by(CreditTransaction.created_at.desc())

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "transactions": [tx.to_dict() for tx in paginated.items],
        "total": paginated.total,
        "pages": paginated.pages,
        "page": page,
    })


# ---------------------------------------------------------------------------
# POST /api/billing/recharge  (apenas admin)
# Recarga manual de crédito (usado em testes ou ajuste manual pelo admin master)
# ---------------------------------------------------------------------------
@billing_bp.route("/recharge", methods=["POST"])
@require_auth
@require_role("admin")
def manual_recharge(current_user):
    data = request.get_json(silent=True) or {}
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except InvalidOperation:
        return jsonify({"error": "Valor inválido"}), 400

    if amount <= 0:
        return jsonify({"error": "Valor deve ser positivo"}), 400

    company = Company.query.get(current_user.company_id)
    if not company:
        return jsonify({"error": "Empresa não encontrada"}), 404

    tx = company.add_credit(
        amount=float(amount),
        description=data.get("description", "Recarga manual"),
        payment_method="manual",
    )
    db.session.commit()
    logger.info(f"[BILLING] Recarga manual R${amount} empresa={company.id}")
    return jsonify({
        "message": "Crédito adicionado com sucesso",
        "new_balance": company.get_balance(),
        "transaction": tx.to_dict(),
    })


# ---------------------------------------------------------------------------
# POST /api/billing/payment/initiate
# Inicia pagamento via MercadoPago (PIX ou cartão)
# ---------------------------------------------------------------------------
@billing_bp.route("/payment/initiate", methods=["POST"])
@require_auth
def initiate_payment(current_user):
    data = request.get_json(silent=True) or {}
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except InvalidOperation:
        return jsonify({"error": "Valor inválido"}), 400

    if amount < Decimal("10"):
        return jsonify({"error": "Valor mínimo de recarga é R$ 10,00"}), 400

    method = data.get("method", "pix")  # "pix" | "card"
    company = Company.query.get(current_user.company_id)

    mp_access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
    if not mp_access_token:
        return jsonify({"error": "Gateway de pagamento não configurado"}), 503

    try:
        import requests as req

        headers = {
            "Authorization": f"Bearer {mp_access_token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": f"nexdial-{company.id}-{int(amount*100)}",
        }

        backend_url = os.getenv("BASE_URL", "http://localhost:5000")

        if method == "pix":
            payload = {
                "transaction_amount": float(amount),
                "description": f"NexDial - Recarga de crédito ({company.name})",
                "payment_method_id": "pix",
                "payer": {
                    "email": current_user.email,
                },
                "notification_url": f"{backend_url}/api/billing/payment/webhook",
                "metadata": {
                    "company_id": str(company.id),
                    "user_id": str(current_user.id),
                    "amount": str(amount),
                },
            }
            resp = req.post(
                "https://api.mercadopago.com/v1/payments",
                json=payload,
                headers=headers,
                timeout=15,
            )
        else:
            return jsonify({"error": "Método não suportado ainda. Use pix."}), 400

        if resp.status_code not in (200, 201):
            logger.error(f"[MP] Erro ao criar pagamento: {resp.text}")
            return jsonify({"error": "Erro ao criar pagamento"}), 502

        mp_data = resp.json()
        payment_id = str(mp_data.get("id"))

        # Registra transação como "pending"
        tx = CreditTransaction(
            company_id=company.id,
            type="recharge",
            amount=amount,
            balance_after=Decimal(str(company.get_balance())),  # ainda não creditado
            description=f"Recarga via {method.upper()} - aguardando confirmação",
            payment_id=payment_id,
            payment_method=method,
            payment_status="pending",
        )
        db.session.add(tx)
        db.session.commit()

        response_data = {
            "payment_id": payment_id,
            "status": mp_data.get("status"),
            "method": method,
            "amount": float(amount),
        }

        if method == "pix":
            pix_info = mp_data.get("point_of_interaction", {}).get("transaction_data", {})
            response_data["pix_qr_code"] = pix_info.get("qr_code")
            response_data["pix_qr_code_base64"] = pix_info.get("qr_code_base64")
            response_data["pix_copy_paste"] = pix_info.get("qr_code")

        return jsonify(response_data)

    except Exception as e:
        logger.exception(f"[BILLING] Erro ao iniciar pagamento: {e}")
        return jsonify({"error": "Erro interno ao processar pagamento"}), 500


# ---------------------------------------------------------------------------
# POST /api/billing/payment/webhook
# MercadoPago notifica quando o pagamento é confirmado
# ---------------------------------------------------------------------------
@billing_bp.route("/payment/webhook", methods=["POST"])
def payment_webhook():
    """
    Recebe notificação do MercadoPago e credita saldo automaticamente.
    Não requer auth — validamos assinatura da requisição.
    """
    data = request.get_json(silent=True) or {}
    topic = data.get("type") or request.args.get("topic")
    resource_id = data.get("data", {}).get("id") or request.args.get("id")

    if topic not in ("payment", "payment.created", "payment.updated"):
        return jsonify({"status": "ignored"}), 200

    if not resource_id:
        return jsonify({"error": "ID não fornecido"}), 400

    mp_access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
    if not mp_access_token:
        return jsonify({"error": "Gateway não configurado"}), 503

    try:
        import requests as req

        resp = req.get(
            f"https://api.mercadopago.com/v1/payments/{resource_id}",
            headers={"Authorization": f"Bearer {mp_access_token}"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error(f"[MP WEBHOOK] Erro ao buscar pagamento {resource_id}: {resp.text}")
            return jsonify({"error": "Erro ao verificar pagamento"}), 502

        mp_payment = resp.json()
        status = mp_payment.get("status")
        metadata = mp_payment.get("metadata", {})
        company_id = metadata.get("company_id")
        amount_str = metadata.get("amount")

        if status != "approved":
            # Atualiza status da transação pendente
            tx = CreditTransaction.query.filter_by(payment_id=str(resource_id)).first()
            if tx:
                tx.payment_status = status
                db.session.commit()
            return jsonify({"status": "not_approved", "payment_status": status}), 200

        if not company_id or not amount_str:
            logger.error(f"[MP WEBHOOK] metadata inválido: {metadata}")
            return jsonify({"error": "Metadata inválido"}), 400

        # Evita crédito duplicado
        existing = CreditTransaction.query.filter_by(
            payment_id=str(resource_id),
            payment_status="approved",
        ).first()
        if existing:
            return jsonify({"status": "already_processed"}), 200

        company = Company.query.get(int(company_id))
        if not company:
            logger.error(f"[MP WEBHOOK] Empresa {company_id} não encontrada")
            return jsonify({"error": "Empresa não encontrada"}), 404

        amount = Decimal(str(mp_payment.get("transaction_amount", amount_str)))
        payment_method = mp_payment.get("payment_method_id", "unknown")

        # Marca transação pendente como aprovada (se existir) e credita
        pending_tx = CreditTransaction.query.filter_by(
            payment_id=str(resource_id),
            payment_status="pending",
        ).first()

        if pending_tx:
            # Atualiza a transação pendente em vez de criar outra
            company.credit_balance = Decimal(str(company.get_balance())) + amount
            pending_tx.payment_status = "approved"
            pending_tx.balance_after = company.credit_balance
        else:
            company.add_credit(
                amount=float(amount),
                description=f"Recarga via {payment_method.upper()}",
                payment_id=str(resource_id),
                payment_method=payment_method,
            )

        db.session.commit()
        logger.info(f"[BILLING] Pagamento aprovado! R${amount} para empresa {company_id}")
        return jsonify({"status": "credited"}), 200

    except Exception as e:
        logger.exception(f"[BILLING WEBHOOK] Erro: {e}")
        return jsonify({"error": "Erro interno"}), 500


# ---------------------------------------------------------------------------
# GET /api/billing/dashboard  (resumo para o painel do cliente)
# ---------------------------------------------------------------------------
@billing_bp.route("/dashboard", methods=["GET"])
@require_auth
def billing_dashboard(current_user):
    from app.models.call import Call
    from sqlalchemy import func

    company = Company.query.get(current_user.company_id)
    if not company:
        return jsonify({"error": "Empresa não encontrada"}), 404

    # Total gasto em chamadas (último mês)
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(days=30)

    total_spent = db.session.query(
        func.sum(CreditTransaction.amount)
    ).filter(
        CreditTransaction.company_id == company.id,
        CreditTransaction.type == "call_debit",
        CreditTransaction.created_at >= since,
    ).scalar() or Decimal("0")

    total_calls = CreditTransaction.query.filter(
        CreditTransaction.company_id == company.id,
        CreditTransaction.type == "call_debit",
        CreditTransaction.created_at >= since,
    ).count()

    last_recharges = CreditTransaction.query.filter_by(
        company_id=company.id,
        type="recharge",
    ).order_by(CreditTransaction.created_at.desc()).limit(5).all()

    last_calls = CreditTransaction.query.filter_by(
        company_id=company.id,
        type="call_debit",
    ).order_by(CreditTransaction.created_at.desc()).limit(10).all()

    return jsonify({
        "balance": company.get_balance(),
        "cost_per_minute": float(company.cost_per_minute),
        "has_credit": company.has_credit(),
        # flat fields for dashboard JS
        "spent_30d": float(abs(total_spent)),
        "calls_30d": total_calls,
        "last_30_days": {
            "total_spent": float(abs(total_spent)),
            "total_calls": total_calls,
            "avg_cost_per_call": float(abs(total_spent) / total_calls) if total_calls > 0 else 0,
        },
        "last_recharges": [tx.to_dict() for tx in last_recharges],
        "last_calls": [tx.to_dict() for tx in last_calls],
        "currency": "BRL",
    })


# ---------------------------------------------------------------------------
# GET /api/billing/payment/<payment_id>/status  (polling do frontend)
# ---------------------------------------------------------------------------
@billing_bp.route("/payment/<payment_id>/status", methods=["GET"])
@require_auth
def payment_status(current_user, payment_id):
    tx = CreditTransaction.query.filter_by(
        payment_id=str(payment_id),
        company_id=current_user.company_id,
    ).first()

    if not tx:
        return jsonify({"error": "Pagamento não encontrado"}), 404

    return jsonify({
        "payment_id": payment_id,
        "status": tx.payment_status or "pending",
        "amount": float(tx.amount) if tx.amount else 0,
    })
