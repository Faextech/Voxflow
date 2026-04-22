import os

from flask import Blueprint, jsonify, g
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

from app.auth import require_auth
from app.models.agent import Agent
from app.models.company import Company

webphone_bp = Blueprint("webphone", __name__, url_prefix="/api/webphone")


@webphone_bp.route("/token/<int:agent_id>", methods=["GET"])
@require_auth
def get_token(agent_id):
    """
    Gera o AccessToken Twilio JS SDK para o webphone do operador.

    Credenciais usadas (em ordem de prioridade):
      1. Campos do tenant na tabela companies (twilio_api_key, etc.)
      2. Variáveis de ambiente do .env (fallback durante migração)

    Segurança:
    - @require_auth exige JWT válido.
    - filter_by(id=..., company_id=g.company_id) garante que o operador
      pertence ao mesmo tenant do usuário autenticado.
    """
    agent = Agent.query.filter_by(id=agent_id, company_id=g.company_id).first()
    if not agent:
        return jsonify({"error": "Operador não encontrado"}), 404

    company = Company.query.get(g.company_id)
    if not company:
        return jsonify({"error": "Empresa não encontrada"}), 404

    creds = company.get_twilio_credentials()

    # Lê credenciais do tenant, com fallback para .env
    account_sid   = (creds.get("account_sid")   or os.getenv("TWILIO_ACCOUNT_SID")   or "").strip()
    api_key       = (creds.get("api_key")        or os.getenv("TWILIO_API_KEY")       or "").strip()
    api_secret    = (creds.get("api_secret")     or os.getenv("TWILIO_API_SECRET")    or "").strip()
    twiml_app_sid = (creds.get("twiml_app_sid")  or os.getenv("TWILIO_TWIML_APP_SID") or "").strip()

    if not account_sid or not api_key or not api_secret:
        return jsonify({"error": "Credenciais Twilio incompletas (account_sid, api_key, api_secret)"}), 500

    if not twiml_app_sid:
        return jsonify({"error": "TWILIO_TWIML_APP_SID não configurado"}), 500

    identity = f"agent_{agent.id}"

    token = AccessToken(
        account_sid,
        api_key,
        api_secret,
        identity=identity,
        ttl=86400,
    )

    voice_grant = VoiceGrant(
        incoming_allow=True,
        outgoing_application_sid=twiml_app_sid,
    )
    token.add_grant(voice_grant)

    jwt_token = token.to_jwt()
    if isinstance(jwt_token, bytes):
        jwt_token = jwt_token.decode("utf-8")

    return jsonify({
        "identity":      identity,
        "token":         jwt_token,
        "twiml_app_sid": twiml_app_sid,
    }), 200
