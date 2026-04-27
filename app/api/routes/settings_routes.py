from flask import Blueprint, jsonify, request, g

from app.auth import require_auth, require_role
from app.extensions import db
from app.models.company import Company
from app.models.user import User
from app.models.lead import Lead
from app.models.call import Call
from app.models.campaign import Campaign
from app.models.deal import Deal

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

@settings_bp.route("/wipe-data", methods=["DELETE"])
@require_auth
@require_role("admin")
def wipe_company_data():
    """
    Apaga todos os dados da empresa (Leads, Deals, Chamadas, Campanhas) 
    após validar a senha do usuário logado.
    """
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    
    if not password:
        return jsonify({"error": "A senha é obrigatória"}), 400
        
    user = User.query.get(g.user_id)
    if not user or not user.check_password(password):
        return jsonify({"error": "Senha incorreta"}), 401

    try:
        # Parar discadores ativos
        from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS
        for c_id, sess in list(AUTO_DIALER_SESSIONS.items()):
            if sess.get("company_id") == g.company_id:
                sess["status"] = "stopped"
                del AUTO_DIALER_SESSIONS[c_id]
    except Exception:
        pass

    try:
        # Apagar dados na ordem correta para não ferir foreign keys
        from app.models.deal_activity import DealActivity
        from app.models.deal_task import DealTask
        from app.models.notification import Notification
        from app.models.callback_queue import CallbackQueue
        
        Notification.query.filter_by(company_id=g.company_id).delete()
        CallbackQueue.query.filter_by(company_id=g.company_id).delete()
        DealActivity.query.filter_by(company_id=g.company_id).delete()
        DealTask.query.filter_by(company_id=g.company_id).delete()
        Call.query.filter_by(company_id=g.company_id).delete()
        Deal.query.filter_by(company_id=g.company_id).delete()
        Lead.query.filter_by(company_id=g.company_id).delete()
        Campaign.query.filter_by(company_id=g.company_id).delete()
        
        db.session.commit()
        return jsonify({"message": "Todos os dados foram apagados com sucesso."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erro ao apagar dados: {str(e)}"}), 500
@settings_bp.route("/regulatory", methods=["GET"])
@require_auth
@require_role("admin")
def get_regulatory_settings():
    company = Company.query.get(g.company_id)
    return jsonify({
        "reg_type": company.reg_type or "business",
        "reg_name": company.reg_name or "",
        "reg_tax_id": company.reg_tax_id or "",
        "reg_address": company.reg_address or "",
        "has_document": bool(company.reg_document_path)
    }), 200

@settings_bp.route("/regulatory", methods=["POST"])
@require_auth
@require_role("admin")
def update_regulatory_settings():
    company = Company.query.get(g.company_id)
    
    # Se houver arquivo (Multipart form data)
    if 'document' in request.files:
        import os
        file = request.files['document']
        if file.filename:
            os.makedirs('storage/regulatory', exist_ok=True)
            path = os.path.join('storage/regulatory', f"doc_{company.id}_{file.filename}")
            file.save(path)
            company.reg_document_path = path

    # Dados do form (Multipart ou JSON)
    data = request.form if request.form else (request.get_json(silent=True) or {})
    
    company.reg_type = data.get('reg_type') or data.get('type')
    company.reg_name = data.get('reg_name') or data.get('name')
    company.reg_tax_id = data.get('reg_tax_id') or data.get('tax_id')
    company.reg_address = data.get('reg_address') or data.get('address')
    
    db.session.commit()
    return jsonify({"message": "Informações de identidade atualizadas com sucesso."}), 200
