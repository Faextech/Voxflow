from flask import Blueprint, jsonify, request, g

from app.auth import require_auth, require_role
from app.extensions import db
from app.models.company import Company

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")

_MASK = "••••••••••••••••••••••••••••••••"


@settings_bp.route("/twilio", methods=["GET"])
@require_auth
@require_role("admin")
def get_twilio_settings():
    """
    Retorna a configuração Twilio do tenant.
    auth_token e api_secret são mascarados — nunca trafegam em claro.
    """
    company = Company.query.get(g.company_id)
    if not company:
        return jsonify({"error": "empresa não encontrada"}), 404

    creds = company.get_twilio_credentials()

    return jsonify({
        "account_sid":    creds["account_sid"]   or "",
        "auth_token":     _MASK if creds["auth_token"]  else "",
        "phone_number":   creds["phone_number"]  or "",
        "api_key":        creds["api_key"]        or "",
        "api_secret":     _MASK if creds["api_secret"] else "",
        "twiml_app_sid":  creds["twiml_app_sid"] or "",
        "configured":     company.has_twilio_configured(),
    }), 200


@settings_bp.route("/twilio", methods=["PUT"])
@require_auth
@require_role("admin")
def update_twilio_settings():
    """
    Atualiza as credenciais Twilio do tenant.

    Regras:
    - Campos não enviados no body são ignorados (valor existente é mantido).
    - Se auth_token ou api_secret forem enviados vazios (""), o campo é limpo.
    - Se forem enviados com o valor mascara (••••), o campo não é alterado.
    - Nunca devolve os valores em claro — retorna GET mascarado após salvar.
    """
    company = Company.query.get(g.company_id)
    if not company:
        return jsonify({"error": "empresa não encontrada"}), 404

    data = request.get_json(silent=True) or {}

    # Para campos sensíveis: None = não veio no body (não altera),
    #                         ""   = veio vazio (limpa o campo),
    #                         _MASK = veio mascarado (não altera),
    #                         valor = atualiza com criptografia.
    def _sensitive(key):
        val = data.get(key)
        if val is None or val == _MASK:
            return None          # sinal de "não mexe"
        return val.strip()       # "" limpa, qualquer outra coisa atualiza

    # Campos não-sensíveis: None = não veio (não altera)
    def _plain(key):
        val = data.get(key)
        if val is None:
            return None
        return val.strip()

    company.set_twilio_credentials(
        account_sid  = _plain("account_sid"),
        auth_token   = _sensitive("auth_token"),
        phone_number = _plain("phone_number"),
        api_key      = _plain("api_key"),
        api_secret   = _sensitive("api_secret"),
        twiml_app_sid= _plain("twiml_app_sid"),
    )

    db.session.commit()

    # Retorna estado atual mascarado
    creds = company.get_twilio_credentials()
    return jsonify({
        "message":       "Configuração Twilio salva com sucesso",
        "account_sid":   creds["account_sid"]   or "",
        "auth_token":    _MASK if creds["auth_token"]  else "",
        "phone_number":  creds["phone_number"]  or "",
        "api_key":       creds["api_key"]        or "",
        "api_secret":    _MASK if creds["api_secret"] else "",
        "twiml_app_sid": creds["twiml_app_sid"] or "",
        "configured":    company.has_twilio_configured(),
    }), 200
