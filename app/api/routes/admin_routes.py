import logging
import random
import string
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, g

from app.auth import require_auth, require_role
from app.extensions import db
from app.models import Company, User
from app.models.billing import CreditTransaction
from app.models.invite_code import InviteCode

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


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
    company_id = request.args.get('company_id')
    
    company = None
    if company_id:
        company = Company.query.get(company_id)
        
    # Se não passar company_id, usamos a master apenas para a busca
    if not company:
        company = Company.query.get(1)

    from app.services.twilio_subaccount_service import search_available_numbers
    numbers = search_available_numbers(company, area_code=area_code)
    return jsonify(numbers)


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
    from app.models.call import Call
    from sqlalchemy import func
    from datetime import date

    total_companies = Company.query.count()

    # Master é a empresa do superadmin logado
    master_company = Company.query.get_or_404(g.company_id)
    master_balance = float(master_company.credit_balance)

    # Crédito na plataforma (soma de todas as outras empresas exceto a master)
    total_clients_credit = db.session.query(func.sum(Company.credit_balance)).filter(Company.id != master_company.id).scalar() or 0

    today = date.today()
    calls_today = Call.query.filter(
        func.date(Call.created_at) == today
    ).count()

    # Receita bruta do mês: soma de débitos de chamada no mês atual de TODOS os clientes
    first_day = today.replace(day=1)
    monthly_revenue = db.session.query(func.sum(CreditTransaction.amount)).filter(
        CreditTransaction.type == 'call_debit',
        CreditTransaction.created_at >= first_day,
    ).scalar() or 0

    return jsonify({
        'total_companies': total_companies,
        'master_balance': master_balance,
        'total_clients_credit': float(total_clients_credit),
        'calls_today': calls_today,
        'monthly_revenue': abs(float(monthly_revenue)),
        # Mantendo para compatibilidade com frontend antigo se necessário
        'total_credit_platform': master_balance + float(total_clients_credit),
    })
