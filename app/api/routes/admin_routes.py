import logging
import os
import random
import string
import time
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, g

from app.auth import require_auth, require_role
from app.extensions import db
from app.models import Company, User
from app.models.billing import CreditTransaction
from app.models.invite_code import InviteCode

logger = logging.getLogger(__name__)

_usd_brl_cache = {'rate': None, 'ts': 0}


def _get_usd_brl_rate() -> float:
    """Busca cotação USD→BRL com cache de 1 hora."""
    now = time.time()
    if _usd_brl_cache['rate'] and (now - _usd_brl_cache['ts']) < 3600:
        return _usd_brl_cache['rate']
    try:
        import requests as req
        r = req.get('https://economia.awesomeapi.com.br/json/last/USD-BRL', timeout=5)
        if r.ok:
            rate = float(r.json()['USDBRL']['bid'])
            _usd_brl_cache['rate'] = rate
            _usd_brl_cache['ts'] = now
            return rate
    except Exception as exc:
        logger.warning('[EXCHANGE] Erro ao buscar USD/BRL: %s', exc)
    env_rate = os.getenv('USD_BRL_RATE')
    if env_rate:
        return float(env_rate)
    return 5.80

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def _fetch_twilio_balance_real():
    """
    Busca o saldo REAL da conta Twilio master via API.
    Retorna (balance_str, currency, error_msg).
    """
    try:
        from twilio.rest import Client
        sid   = (os.getenv('TWILIO_ACCOUNT_SID') or '').strip()
        token = (os.getenv('TWILIO_AUTH_TOKEN')  or '').strip()
        if not sid or not token:
            return None, None, 'TWILIO_ACCOUNT_SID ou TWILIO_AUTH_TOKEN não configurados'
        client = Client(sid, token)
        # Caminho mais direto em versões recentes do SDK
        balance = client.balance.fetch()
        logger.info('[TWILIO] Saldo real buscado: %s %s', balance.balance, balance.currency)
        return balance.balance, balance.currency, None
    except Exception as exc:
        logger.error('[TWILIO] Erro ao buscar saldo real: %s', exc)
        return None, None, str(exc)


def _require_superadmin(f):
    from functools import wraps
    @wraps(f)
    @require_auth
    @require_role('superadmin')
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapper


# ── Gestão de empresas ────────────────────────────────────────────────────────

@admin_bp.route('/companies', methods=['GET'])
@require_auth
@require_role('superadmin')
def list_companies():
    companies = Company.query.order_by(Company.created_at.desc()).all()
    result = []
    for c in companies:
        user_count = User.query.filter_by(company_id=c.id).count()
        admin_user = User.query.filter_by(company_id=c.id, role='admin').first()
        result.append({
            'id': c.id,
            'name': c.name,
            'email': c.email,
            'plan': c.plan,
            'status': c.status,
            'credit_balance': float(c.credit_balance or 0),
            'cost_per_minute': float(c.cost_per_minute or 0),
            'twilio_subaccount_sid': c.twilio_subaccount_sid,
            'user_count': user_count,
            'created_at': c.created_at.isoformat() if c.created_at else None,
            'admin_name': admin_user.name if admin_user else None,
            'admin_email': admin_user.email if admin_user else None,
        })
    return jsonify(result)


@admin_bp.route('/companies/<int:company_id>/regulatory', methods=['POST'])
@require_auth
@require_role('superadmin')
def update_regulatory(company_id):
    company = Company.query.get_or_404(company_id)
    
    # Se houver arquivo
    if 'document' in request.files:
        file = request.files['document']
        if file.filename:
            # Garante diretório
            os.makedirs('storage/regulatory', exist_ok=True)
            path = os.path.join('storage/regulatory', f"doc_{company.id}_{file.filename}")
            file.save(path)
            company.reg_document_path = path

    data = request.form
    company.reg_type = data.get('type')
    company.reg_name = data.get('name')
    company.reg_tax_id = data.get('tax_id')
    company.reg_address = data.get('address')
    
    db.session.commit()
    logger.info(f"Regulatory Info persistida para {company.id}")
    
    return jsonify({'ok': True, 'message': 'Informações salvas e persistidas!'})


@admin_bp.route('/companies/<int:company_id>', methods=['GET'])
@require_auth
@require_role('superadmin')
def get_company(company_id):
    company = Company.query.get_or_404(company_id)
    users = User.query.filter_by(company_id=company.id).all()
    txs = (
        CreditTransaction.query
        .filter_by(company_id=company.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(10)
        .all()
    )
    return jsonify({
        'id': company.id,
        'name': company.name,
        'email': company.email,
        'plan': company.plan,
        'status': company.status,
        'credit_balance': float(company.credit_balance or 0),
        'cost_per_minute': float(company.cost_per_minute or 0),
        'twilio_subaccount_sid': company.twilio_subaccount_sid,
        'twilio_number': company.twilio_number,
        'reg_type': company.reg_type,
        'reg_name': company.reg_name,
        'reg_tax_id': company.reg_tax_id,
        'reg_address': company.reg_address,
        'reg_document_path': company.reg_document_path,
        'has_twilio': company.has_twilio_configured(),
        'created_at': company.created_at.isoformat() if company.created_at else None,
        'users': [{'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role, 'status': u.status} for u in users],
        'recent_transactions': [t.to_dict() for t in txs],
    })


@admin_bp.route('/companies/<int:company_id>', methods=['PATCH'])
@require_auth
@require_role('superadmin')
def update_company(company_id):
    company = Company.query.get_or_404(company_id)
    data = request.get_json() or {}

    if 'name' in data:
        company.name = data['name']
    if 'cost_per_minute' in data:
        from decimal import Decimal
        company.cost_per_minute = Decimal(str(data['cost_per_minute']))
    if 'plan' in data and data['plan'] in ('starter', 'pro', 'enterprise'):
        company.plan = data['plan']
    if 'status' in data and data['status'] in ('active', 'suspended', 'inactive'):
        company.status = data['status']

    db.session.commit()
    return jsonify({'ok': True, 'id': company.id})


@admin_bp.route('/companies/<int:company_id>/add-credit', methods=['POST'])
@require_auth
@require_role('superadmin')
def add_credit(company_id):
    target_company = Company.query.get_or_404(company_id)
    # Master é a empresa do superadmin logado
    master_company = Company.query.get_or_404(g.company_id)

    data = request.get_json() or {}
    amount = float(data.get('amount', 0))
    description = data.get('description', '')

    if amount <= 0:
        return jsonify({'error': 'Valor deve ser positivo'}), 400

    if master_company.id == target_company.id:
        # Se for para si mesmo (master depositando nela mesma), usamos add_credit normal
        # Isso seria como um "Ajuste manual" ou "Depósito bancário"
        target_company.add_credit(amount, description=description or "Depósito direto na master", tx_type="manual_adjust")
    else:
        # Transferência da Master para o Cliente
        try:
            master_company.transfer_credit(target_company, amount, description=description)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

    db.session.commit()
    return jsonify({
        'ok': True,
        'new_balance': float(target_company.credit_balance),
        'master_balance': float(master_company.credit_balance)
    })


@admin_bp.route('/available-numbers', methods=['GET'])
@require_auth
@require_role('superadmin')
def list_available_numbers():
    area_code = request.args.get('area_code', '11')
    from app.services.twilio_subaccount_service import search_available_numbers
    result = search_available_numbers(area_code=area_code)
    # result pode ser list (sucesso) ou dict {'numbers': [], 'error': '...'}
    if isinstance(result, dict):
        # Retorna com status 207 para que o frontend saiba que houve problema
        status = 200 if result.get('numbers') else 502
        return jsonify(result), status
    return jsonify(result)


@admin_bp.route('/companies/<int:company_id>/twilio-numbers', methods=['GET'])
@require_auth
@require_role('superadmin')
def list_sub_numbers(company_id):
    company = Company.query.get_or_404(company_id)
    from app.services.twilio_subaccount_service import list_subaccount_numbers
    numbers = list_subaccount_numbers(company)
    return jsonify(numbers)


@admin_bp.route('/companies/<int:company_id>/configure-number', methods=['POST'])
@require_auth
@require_role('superadmin')
def config_sub_number(company_id):
    company = Company.query.get_or_404(company_id)
    data = request.get_json() or {}
    phone_number = data.get('phone_number')
    if not phone_number:
        return jsonify({'error': 'Número é obrigatório'}), 400
        
    from app.services.twilio_subaccount_service import configure_existing_number
    success = configure_existing_number(company, phone_number)
    return jsonify({'ok': success})


@admin_bp.route('/companies/<int:company_id>/create-subaccount', methods=['POST'])
@require_auth
@require_role('superadmin')
def create_subaccount_route(company_id):
    company = Company.query.get_or_404(company_id)
    data = request.get_json() or {}
    phone_number = data.get('phone_number')

    if company.twilio_subaccount_sid and company.twilio_number:
        return jsonify({'ok': True, 'already_exists': True, 'sid': company.twilio_subaccount_sid, 'number': company.twilio_number})
    try:
        from app.services.twilio_subaccount_service import setup_full_company
        result = setup_full_company(company, phone_number=phone_number)
        return jsonify(result)
    except Exception as e:
        logger.error(f"[ADMIN] Erro no setup completo para empresa {company_id}: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/companies/<int:company_id>/suspend', methods=['POST'])
@require_auth
@require_role('superadmin')
def suspend_company(company_id):
    company = Company.query.get_or_404(company_id)
    try:
        from app.services.twilio_subaccount_service import suspend_subaccount
        ok = suspend_subaccount(company)
        if ok:
            company.status = 'suspended'
            db.session.commit()
        return jsonify({'ok': ok})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/companies/<int:company_id>/activate', methods=['POST'])
@require_auth
@require_role('superadmin')
def activate_company(company_id):
    company = Company.query.get_or_404(company_id)
    try:
        from app.services.twilio_subaccount_service import activate_subaccount
        ok = activate_subaccount(company)
        if ok:
            company.status = 'active'
            db.session.commit()
        return jsonify({'ok': ok})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Gestão de convites ────────────────────────────────────────────────────────

@admin_bp.route('/invite-codes', methods=['GET'])
@require_auth
@require_role('superadmin')
def list_invite_codes():
    codes = InviteCode.query.order_by(InviteCode.created_at.desc()).all()
    result = []
    for c in codes:
        company_name = None
        if c.used_by_company_id:
            comp = Company.query.get(c.used_by_company_id)
            company_name = comp.name if comp else None
        result.append({
            'id': c.id,
            'code': c.code,
            'used': c.used,
            'used_by_company_id': c.used_by_company_id,
            'used_by_company_name': company_name,
            'used_at': c.used_at.isoformat() if c.used_at else None,
            'created_at': c.created_at.isoformat() if c.created_at else None,
            'expires_at': c.expires_at.isoformat() if c.expires_at else None,
            'valid': c.is_valid(),
        })
    return jsonify(result)


@admin_bp.route('/invite-codes', methods=['POST'])
@require_auth
@require_role('superadmin')
def create_invite_code():
    data = request.get_json() or {}
    expires_in_days = data.get('expires_in_days')

    # Gera código no formato VXF-XXXXXX
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    code = f"VXF-{suffix}"

    # Garante unicidade
    while InviteCode.query.filter_by(code=code).first():
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        code = f"VXF-{suffix}"

    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=int(expires_in_days))

    invite = InviteCode(code=code, expires_at=expires_at)
    db.session.add(invite)
    db.session.commit()

    return jsonify({
        'id': invite.id,
        'code': invite.code,
        'expires_at': invite.expires_at.isoformat() if invite.expires_at else None,
        'created_at': invite.created_at.isoformat() if invite.created_at else None,
    }), 201


@admin_bp.route('/invite-codes/<int:code_id>', methods=['DELETE'])
@require_auth
@require_role('superadmin')
def delete_invite_code(code_id):
    invite = InviteCode.query.get_or_404(code_id)
    if invite.used:
        return jsonify({'error': 'Não é possível deletar um código já utilizado'}), 400
    db.session.delete(invite)
    db.session.commit()
    return jsonify({'ok': True})


# ── Dashboard geral ───────────────────────────────────────────────────────────

@admin_bp.route('/dashboard', methods=['GET'])
@require_auth
@require_role('superadmin')
def admin_dashboard():
    from sqlalchemy import text
    from datetime import date

    today = date.today()
    first_day = today.replace(day=1)

    with db.engine.connect() as conn:
        total_companies = conn.execute(text("SELECT COUNT(*) FROM companies")).scalar() or 0

        row = conn.execute(
            text("SELECT credit_balance FROM companies WHERE id = :cid"),
            {"cid": g.company_id}
        ).fetchone()
        master_balance = float(row[0]) if row and row[0] is not None else 0.0

        total_clients_credit = conn.execute(
            text("SELECT COALESCE(SUM(credit_balance), 0) FROM companies WHERE id != :cid"),
            {"cid": g.company_id}
        ).scalar() or 0

        calls_today = conn.execute(
            text("SELECT COUNT(*) FROM calls WHERE DATE(created_at) = :today"),
            {"today": today}
        ).scalar() or 0

        monthly_revenue = conn.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) FROM credit_transactions
                WHERE type = 'call_debit' AND created_at >= :first_day
            """),
            {"first_day": first_day}
        ).scalar() or 0

    # ── Saldo REAL da conta Twilio master ─────────────────────────────────────
    twilio_balance, twilio_currency, twilio_error = _fetch_twilio_balance_real()

    twilio_balance_brl = None
    usd_brl_rate = None
    if twilio_balance:
        usd_brl_rate = _get_usd_brl_rate()
        twilio_balance_brl = round(float(twilio_balance) * usd_brl_rate, 2)

    return jsonify({
        'total_companies':      total_companies,
        'master_balance':       master_balance,
        'total_clients_credit': float(total_clients_credit),
        'calls_today':          calls_today,
        'monthly_revenue':      abs(float(monthly_revenue)),
        'total_credit_platform': master_balance + float(total_clients_credit),
        # Saldo real da conta Twilio (USD) — None se falhou
        'twilio_balance':       twilio_balance,
        'twilio_balance_brl':   twilio_balance_brl,
        'twilio_currency':      twilio_currency or 'USD',
        'usd_brl_rate':         usd_brl_rate,
        'twilio_error':         twilio_error,
    })


# ── Diagnóstico Twilio ────────────────────────────────────────────────────────

@admin_bp.route('/twilio-diagnostics', methods=['GET'])
@require_auth
@require_role('superadmin')
def twilio_diagnostics():
    """
    Testa TODAS as integrações Twilio e retorna status real de cada uma.
    Use para diagnosticar problemas em produção.
    """
    import os
    result = {}

    # 1. Variáveis de ambiente
    env_vars = [
        'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN',
        'TWILIO_API_KEY', 'TWILIO_API_SECRET',
        'TWILIO_TWIML_APP_SID', 'TWILIO_PHONE_NUMBER',
        'PUBLIC_BASE_URL', 'BASE_URL', 'FERNET_KEY',
        'TWILIO_BUNDLE_SID', 'TWILIO_ADDRESS_SID',
    ]
    result['env_vars'] = {}
    for var in env_vars:
        val = os.getenv(var)
        if val:
            # Mostra só os primeiros e últimos chars (segurança)
            display = val[:6] + '...' + val[-4:] if len(val) > 10 else '***'
            result['env_vars'][var] = {'set': True, 'preview': display}
        else:
            result['env_vars'][var] = {'set': False, 'preview': 'NÃO CONFIGURADO'}

    # 2. Teste do client Twilio
    try:
        from twilio.rest import Client
        sid   = (os.getenv('TWILIO_ACCOUNT_SID') or '').strip()
        token = (os.getenv('TWILIO_AUTH_TOKEN')  or '').strip()
        client = Client(sid, token)

        # 2a. Saldo real
        try:
            bal = client.balance.fetch()
            result['twilio_balance'] = {
                'ok': True,
                'balance': bal.balance,
                'currency': bal.currency,
            }
        except Exception as e:
            result['twilio_balance'] = {'ok': False, 'error': str(e)}

        # 2b. TwiML App
        twiml_app_sid = (os.getenv('TWILIO_TWIML_APP_SID') or '').strip()
        if twiml_app_sid:
            try:
                app = client.applications(twiml_app_sid).fetch()
                result['twiml_app'] = {
                    'ok': True,
                    'sid': app.sid,
                    'friendly_name': app.friendly_name,
                    'voice_url': app.voice_url,
                    'voice_method': app.voice_method,
                }
                public_url = (os.getenv('PUBLIC_BASE_URL') or '').strip()
                if public_url and public_url not in (app.voice_url or ''):
                    result['twiml_app']['warning'] = (
                        f'voice_url ({app.voice_url}) NÃO contém PUBLIC_BASE_URL ({public_url}). '
                        'O webphone NÃO vai funcionar em produção! '
                        'Use POST /api/admin/update-twiml-app para corrigir.'
                    )
            except Exception as e:
                result['twiml_app'] = {'ok': False, 'sid': twiml_app_sid, 'error': str(e)}
        else:
            result['twiml_app'] = {'ok': False, 'error': 'TWILIO_TWIML_APP_SID não configurado'}

        # 2c. Números disponíveis (BR) — busca rápida
        try:
            nums = client.available_phone_numbers('BR').local.list(limit=2)
            result['available_numbers'] = {
                'ok': True,
                'count': len(nums),
                'sample': [n.phone_number for n in nums],
            }
        except Exception as e:
            result['available_numbers'] = {'ok': False, 'error': str(e)}

        # 2d. API Key/Secret (gera token de teste)
        api_key    = (os.getenv('TWILIO_API_KEY')    or '').strip()
        api_secret = (os.getenv('TWILIO_API_SECRET') or '').strip()
        if api_key and api_secret:
            try:
                from twilio.jwt.access_token import AccessToken
                test_token = AccessToken(sid, api_key, api_secret, identity='test_diag', ttl=60)
                test_token.to_jwt()
                result['access_token_generation'] = {'ok': True}
            except Exception as e:
                result['access_token_generation'] = {'ok': False, 'error': str(e)}
        else:
            result['access_token_generation'] = {'ok': False, 'error': 'TWILIO_API_KEY ou TWILIO_API_SECRET não configurados'}

    except Exception as e:
        result['twilio_client'] = {'ok': False, 'error': str(e)}

    # 3. FERNET_KEY (criptografia de credenciais)
    fernet_key = os.getenv('FERNET_KEY')
    if fernet_key:
        try:
            from cryptography.fernet import Fernet
            Fernet(fernet_key.encode())
            result['fernet'] = {'ok': True}
        except Exception as e:
            result['fernet'] = {'ok': False, 'error': str(e)}
    else:
        result['fernet'] = {'ok': False, 'error': 'FERNET_KEY não configurado'}

    result['public_base_url'] = os.getenv('PUBLIC_BASE_URL') or 'NÃO CONFIGURADO'
    result['flask_env']       = os.getenv('FLASK_ENV')       or 'NÃO CONFIGURADO'

    return jsonify(result)


@admin_bp.route('/update-twiml-app', methods=['POST'])
@require_auth
@require_role('superadmin')
def update_twiml_app():
    """
    Atualiza a voice_url do TwiML App para apontar para PUBLIC_BASE_URL.
    Necessário quando o app foi criado apontando para localhost.
    """
    try:
        from twilio.rest import Client
        sid        = (os.getenv('TWILIO_ACCOUNT_SID')  or '').strip()
        token      = (os.getenv('TWILIO_AUTH_TOKEN')   or '').strip()
        app_sid    = (os.getenv('TWILIO_TWIML_APP_SID') or '').strip()
        public_url = (os.getenv('PUBLIC_BASE_URL') or os.getenv('BASE_URL') or '').strip().rstrip('/')

        if not all([sid, token, app_sid, public_url]):
            return jsonify({'error': 'TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_TWIML_APP_SID e PUBLIC_BASE_URL são obrigatórios'}), 400

        client = Client(sid, token)
        new_voice_url    = f'{public_url}/api/twilio/browser-outgoing'
        new_status_cb    = f'{public_url}/api/twilio/status'

        app = client.applications(app_sid).update(
            voice_url=new_voice_url,
            voice_method='POST',
            status_callback=new_status_cb,
            status_callback_method='POST',
        )
        logger.info('[ADMIN] TwiML App %s atualizado: voice_url=%s', app_sid, new_voice_url)
        return jsonify({
            'ok': True,
            'app_sid': app.sid,
            'voice_url': app.voice_url,
            'status_callback': app.status_callback,
        })
    except Exception as e:
        logger.error('[ADMIN] Erro ao atualizar TwiML App: %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500
