from flask import Blueprint, jsonify, request, g

from app.auth import require_auth, require_role, log_audit
from app.extensions import db
from app.models.company import Company
from app.models.user import User
from app.models.lead import Lead
from app.models.call import Call
from app.models.campaign import Campaign
from app.models.deal import Deal

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")

_MASK = "••••••••••••••••••••••••••••••••"


@settings_bp.route("/company", methods=["GET"])
@require_auth
def get_company_settings():
    company = Company.query.get(g.company_id)
    if not company:
        return jsonify({"error": "Empresa não encontrada"}), 404
    return jsonify({
        "name":    company.name    or "",
        "segment": company.segment or "",
    }), 200


@settings_bp.route("/company", methods=["PUT"])
@require_auth
@require_role("admin")
def update_company_settings():
    data    = request.get_json(silent=True) or {}
    company = Company.query.get(g.company_id)
    if not company:
        return jsonify({"error": "Empresa não encontrada"}), 404

    name    = (data.get("name") or "").strip()
    segment = (data.get("segment") or "").strip()

    if name:
        company.name    = name
    company.segment = segment or None

    db.session.commit()
    log_audit("update_company_settings", resource_type="company", resource_id=g.company_id,
              changes={"name": company.name, "segment": company.segment})
    return jsonify({"message": "Configurações salvas", "name": company.name, "segment": company.segment}), 200


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

@settings_bp.route("/twilio/test", methods=["POST"])
@require_auth
@require_role("admin")
def test_twilio_connection():
    """Valida as credenciais Twilio do tenant fazendo um fetch da conta."""
    from app.services.twilio_service import TwilioService
    company = Company.query.get(g.company_id)
    if not company:
        return jsonify({"error": "Empresa não encontrada"}), 404
    if not company.has_twilio_configured():
        return jsonify({"error": "Credenciais Twilio não configuradas"}), 400
    try:
        svc = TwilioService.from_company(company, current_user_email=getattr(g, "user_email", None))
        account = svc.client.api.accounts(svc.account_sid).fetch()
        return jsonify({
            "ok":           True,
            "account_name": account.friendly_name,
            "status":       account.status,
        }), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 422


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
        log_audit('wipe_company_data', resource_type='company', resource_id=g.company_id,
                  changes={'action': 'full_wipe'})
        return jsonify({"message": "Todos os dados foram apagados com sucesso."}), 200
    except Exception as e:
        db.session.rollback()
        log_audit('wipe_company_data', resource_type='company', resource_id=g.company_id,
                  status='failed', error_message=str(e))
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


# ── 2FA TOTP (SEC-03) ─────────────────────────────────────────────────────────

@settings_bp.route("/2fa/setup", methods=["POST"])
@require_auth
def setup_2fa():
    """
    Gera (ou regenera) o secret TOTP do usuário e retorna o QR code como base64.
    O 2FA ainda NÃO está ativo — o usuário precisa confirmar com /2fa/verify.
    """
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    # Gera novo secret (desativa 2FA temporariamente até confirmar)
    secret = user.generate_totp_secret()
    db.session.commit()

    qr_base64 = user.get_totp_qrcode_base64(issuer="VoxFlow")

    log_audit("2fa_setup_initiated", resource_type="user", resource_id=user.id)
    return jsonify({
        "message":   "QR code gerado. Escaneie com Google Authenticator e confirme com /2fa/verify.",
        "secret":    secret,           # exibido como backup manual
        "qr_base64": qr_base64,        # PNG base64 para <img src="data:image/png;base64,...">
        "totp_uri":  user.get_totp_uri(),
    }), 200


@settings_bp.route("/2fa/verify", methods=["POST"])
@require_auth
def verify_2fa():
    """
    Ativa o 2FA confirmando o primeiro código TOTP gerado pelo app autenticador.
    Payload: { "code": "123456" }
    """
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    if not user.totp_secret:
        return jsonify({"error": "Execute /2fa/setup primeiro para gerar o QR code"}), 400

    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().replace(" ", "")

    if len(code) != 6 or not code.isdigit():
        return jsonify({"error": "Código inválido — deve ter 6 dígitos"}), 400

    if not user.verify_totp(code):
        log_audit("2fa_verify_failed", resource_type="user", resource_id=user.id)
        return jsonify({"error": "Código TOTP incorreto ou expirado"}), 400

    user.totp_enabled = True
    db.session.commit()

    log_audit("2fa_enabled", resource_type="user", resource_id=user.id)
    return jsonify({
        "message":      "Autenticação de dois fatores ativada com sucesso.",
        "totp_enabled": True,
    }), 200


@settings_bp.route("/2fa/disable", methods=["POST"])
@require_auth
def disable_2fa():
    """
    Desativa o 2FA. Requer senha do usuário por segurança.
    Payload: { "password": "...", "code": "123456" }
    """
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    code     = str(data.get("code", "")).strip().replace(" ", "")

    if not user.check_password(password):
        return jsonify({"error": "Senha incorreta"}), 401

    if user.totp_enabled and (len(code) != 6 or not user.verify_totp(code)):
        return jsonify({"error": "Código TOTP inválido"}), 400

    user.totp_enabled = False
    user.totp_secret  = None
    db.session.commit()

    log_audit("2fa_disabled", resource_type="user", resource_id=user.id)
    return jsonify({"message": "Autenticação de dois fatores desativada.", "totp_enabled": False}), 200


@settings_bp.route("/2fa/status", methods=["GET"])
@require_auth
def status_2fa():
    """Retorna se o 2FA está ativo para o usuário logado."""
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404
    return jsonify({
        "totp_enabled": bool(user.totp_enabled),
        "email":        user.email,
    }), 200

