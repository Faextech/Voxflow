import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, make_response, redirect, request, current_app, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import Company, User
from app.models.agent import Agent
from app.models.pipeline import Pipeline, PipelineStage
from app.models.invite_code import InviteCode
from app.auth import (
    generate_jwt_token,
    generate_refresh_token,
    generate_csrf_token,
    generate_2fa_challenge_token,
    verify_jwt_token,
    revoke_refresh_token,
    revoke_token,
    check_rate_limit,
    log_audit,
)

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    name         = data.get('name', 'Administrador')
    email        = (data.get('email') or '').strip().lower()
    password     = data.get('password')
    company_name = data.get('company_name', 'Minha Empresa')
    phone        = (data.get('phone') or '').strip()
    invite_code  = (data.get('invite_code') or '').strip()

    if not email or not password:
        return jsonify({'error': 'Email e senha são obrigatórios'}), 400

    if not invite_code:
        return jsonify({'error': 'Código de convite é obrigatório'}), 400

    invite = InviteCode.query.filter_by(code=invite_code).first()
    if not invite or not invite.is_valid():
        return jsonify({'error': 'Código de convite inválido ou já utilizado'}), 403

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email já cadastrado'}), 400

    company = Company(name=company_name, email=email, phone=phone or None)
    db.session.add(company)
    db.session.flush()

    user = User(
        company_id    = company.id,
        name          = name,
        email         = email,
        password_hash = generate_password_hash(password, method='pbkdf2:sha256'),
        role          = 'admin',
    )
    db.session.add(user)
    db.session.flush()

    agent = Agent(company_id=company.id, user_id=user.id, status='offline')
    db.session.add(agent)
    db.session.commit()

    # Pipeline padrão
    _pipeline = Pipeline(
        company_id  = company.id,
        name        = "Comercial",
        description = "Pipeline padrão de vendas criado automaticamente",
        color       = "#6366f1",
        is_default  = True,
        position    = 0,
    )
    db.session.add(_pipeline)
    db.session.flush()
    _stages = [
        {"name": "Novos Leads",       "color": "#6366f1", "prob": 5,   "is_won": False, "is_lost": False},
        {"name": "Em Contato",        "color": "#3b82f6", "prob": 15,  "is_won": False, "is_lost": False},
        {"name": "Qualificado",       "color": "#f59e0b", "prob": 40,  "is_won": False, "is_lost": False},
        {"name": "Reunião Agendada",  "color": "#8b5cf6", "prob": 60,  "is_won": False, "is_lost": False},
        {"name": "Proposta Enviada",  "color": "#06b6d4", "prob": 75,  "is_won": False, "is_lost": False},
        {"name": "Ganho",             "color": "#22c55e", "prob": 100, "is_won": True,  "is_lost": False},
        {"name": "Perdido",           "color": "#ef4444", "prob": 0,   "is_won": False, "is_lost": True},
        {"name": "Não Atendeu",       "color": "#6b7280", "prob": 5,   "is_won": False, "is_lost": False},
        {"name": "Caixa Postal",      "color": "#9ca3af", "prob": 5,   "is_won": False, "is_lost": False},
        {"name": "Inválido",          "color": "#374151", "prob": 0,   "is_won": False, "is_lost": True},
    ]
    for _i, _s in enumerate(_stages):
        db.session.add(PipelineStage(
            pipeline_id         = _pipeline.id,
            company_id          = company.id,
            name                = _s["name"],
            position            = _i,
            color               = _s["color"],
            is_won              = _s["is_won"],
            is_lost             = _s["is_lost"],
            default_probability = _s["prob"],
        ))
    db.session.commit()

    invite.used                = True
    invite.used_by_company_id  = company.id
    invite.used_at             = datetime.utcnow()
    db.session.commit()

    try:
        from app.services.twilio_subaccount_service import create_subaccount
        create_subaccount(company)
        logger.info(f"[REGISTER] Subconta Twilio criada para empresa {company.id}")
    except Exception as e:
        logger.error(f"[REGISTER] Falha ao criar subconta Twilio empresa {company.id}: {e}")

    return jsonify({
        'message':    'Conta criada com sucesso',
        'company_id': company.id,
        'user_id':    user.id,
    }), 201

@auth_bp.route('/login', methods=['GET'])
def login_get():
    return redirect(url_for('pages.login_page'))

@auth_bp.route('/login', methods=['POST'])
def login():
    data  = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email e senha são obrigatórios'}), 400

    # Rate limiting por IP: 5 tentativas / 60s (Redis-backed)
    ip_key = f"login:{request.remote_addr}"
    if not check_rate_limit(ip_key, max_attempts=5, window_seconds=60):
        logger.warning("[AUTH] Rate limit atingido para IP %s", request.remote_addr)
        return jsonify({'error': 'Muitas tentativas. Tente novamente em 60 segundos.'}), 429

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        log_audit('login_failed', resource_type='user', changes={'email': email}, status='failed',
                  error_message='Credenciais inválidas')
        return jsonify({'error': 'Credenciais inválidas'}), 401

    if user.status != 'active':
        log_audit('login_failed', resource_type='user', resource_id=user.id,
                  changes={'email': email}, status='failed', error_message='Conta inativa')
        return jsonify({'error': 'Conta inativa. Contate o suporte.'}), 403

    # ── 2FA: se ativado, emite challenge token em vez dos cookies definitivos ──
    if getattr(user, 'totp_enabled', False):
        challenge_token = generate_2fa_challenge_token(user.id)
        is_production   = not current_app.config.get('DEBUG', False)
        resp = make_response(jsonify({
            'requires_2fa':   True,
            'challenge_token': challenge_token,
            'message':        'Código de autenticação necessário',
        }), 200)
        resp.set_cookie(
            'voxflow_2fa_challenge',
            challenge_token,
            httponly = True,
            secure   = is_production,
            samesite = 'Lax',
            max_age  = 300,   # 5 minutos
        )
        log_audit('login_2fa_challenge', resource_type='user', resource_id=user.id,
                  changes={'email': user.email})
        return resp

    access_token  = generate_jwt_token(user.id, user.company_id, user.role)
    refresh_token = generate_refresh_token(user.id, user.company_id, user.role)

    agent_id = user.agent_profile.id if user.agent_profile else None

    is_production = not current_app.config.get('DEBUG', False)
    access_max_age  = int(timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']).total_seconds())
    refresh_max_age = int(timedelta(days=current_app.config['JWT_REFRESH_EXPIRATION_DAYS']).total_seconds())

    resp = make_response(jsonify({
        'message':    'Login realizado com sucesso',
        'token':      access_token,
        'user_id':    user.id,
        'company_id': user.company_id,
        'agent_id':   agent_id,
        'email':      user.email,
        'name':       user.name,
        'role':       user.role,
        'token_expires_in': access_max_age,
    }), 200)

    resp.set_cookie(
        'voxflow_token',
        access_token,
        httponly = True,
        secure   = is_production,
        samesite = 'Lax',
        max_age  = access_max_age,
    )
    resp.set_cookie(
        'voxflow_refresh',
        refresh_token,
        httponly = True,
        secure   = is_production,
        samesite = 'Lax',
        max_age  = refresh_max_age,
        path     = '/auth/refresh',  # cookie só enviado para o endpoint de refresh
    )
    # CSRF: cookie legível por JS (não HttpOnly) — JS envia como X-CSRF-Token header
    resp.set_cookie(
        'voxflow_csrf',
        generate_csrf_token(),
        httponly = False,
        secure   = is_production,
        samesite = 'Lax',
        max_age  = access_max_age,
    )

    log_audit('login_success', resource_type='user', resource_id=user.id,
              changes={'email': user.email, 'role': user.role})
    return resp



@auth_bp.route('/login/2fa', methods=['POST'])
def login_2fa():
    """
    Segunda etapa do login quando 2FA está ativado.
    Payload JSON: { "challenge_token": "...", "code": "123456" }
    O challenge_token pode vir do JSON body ou do cookie voxflow_2fa_challenge.
    """
    data  = request.get_json(silent=True) or {}
    token = data.get('challenge_token') or request.cookies.get('voxflow_2fa_challenge', '')
    code  = str(data.get('code', '')).strip().replace(' ', '')

    if not token:
        return jsonify({'error': 'Token de desafio ausente. Faça login novamente.'}), 400

    payload = verify_jwt_token(token)
    if not payload or payload.get('type') != '2fa_challenge':
        return jsonify({'error': 'Token de desafio inválido ou expirado. Faça login novamente.'}), 401

    if len(code) != 6 or not code.isdigit():
        return jsonify({'error': 'Código inválido — deve ter 6 dígitos numéricos'}), 400

    user = User.query.get(payload.get('user_id'))
    if not user or user.status != 'active':
        return jsonify({'error': 'Usuário inválido ou inativo'}), 401

    if not user.verify_totp(code):
        log_audit('login_2fa_failed', resource_type='user', resource_id=user.id,
                  changes={'email': user.email})
        return jsonify({'error': 'Código TOTP incorreto ou expirado. Tente novamente.'}), 400

    # Autenticação completa — emite tokens definitivos
    access_token  = generate_jwt_token(user.id, user.company_id, user.role)
    refresh_token = generate_refresh_token(user.id, user.company_id, user.role)
    agent_id      = user.agent_profile.id if user.agent_profile else None

    is_production   = not current_app.config.get('DEBUG', False)
    access_max_age  = int(timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']).total_seconds())
    refresh_max_age = int(timedelta(days=current_app.config['JWT_REFRESH_EXPIRATION_DAYS']).total_seconds())

    resp = make_response(jsonify({
        'message':          'Login realizado com sucesso (2FA verificado)',
        'token':            access_token,
        'user_id':          user.id,
        'company_id':       user.company_id,
        'agent_id':         agent_id,
        'email':            user.email,
        'name':             user.name,
        'role':             user.role,
        'token_expires_in': access_max_age,
    }), 200)
    resp.set_cookie('voxflow_token',   access_token,         httponly=True, secure=is_production, samesite='Lax', max_age=access_max_age)
    resp.set_cookie('voxflow_refresh', refresh_token,        httponly=True, secure=is_production, samesite='Lax', max_age=refresh_max_age, path='/auth/refresh')
    resp.set_cookie('voxflow_csrf',    generate_csrf_token(), httponly=False, secure=is_production, samesite='Lax', max_age=access_max_age)
    resp.delete_cookie('voxflow_2fa_challenge')

    log_audit('login_success_2fa', resource_type='user', resource_id=user.id,
              changes={'email': user.email, 'role': user.role})
    return resp


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """
    Renova o access token usando o refresh token.
    Pode ser chamado silenciosamente pelo frontend quando o access token expira.
    """
    refresh_token = request.cookies.get('voxflow_refresh') or (request.get_json(silent=True) or {}).get('refresh_token')

    if not refresh_token:
        return jsonify({'error': 'Refresh token não encontrado'}), 401

    payload = verify_jwt_token(refresh_token)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'error': 'Refresh token inválido ou expirado'}), 401

    jti = payload.get('jti', '')
    try:
        from app.services import redis_service
        if not redis_service.exists(f"refresh_jti:{jti}"):
            return jsonify({'error': 'Refresh token revogado'}), 401
    except Exception:
        pass

    user = User.query.get(payload.get('user_id'))
    if not user or user.status != 'active':
        return jsonify({'error': 'Usuário inválido'}), 401

    new_access = generate_jwt_token(user.id, user.company_id, user.role)
    is_production = not current_app.config.get('DEBUG', False)
    access_max_age = int(timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']).total_seconds())

    resp = make_response(jsonify({
        'token':           new_access,
        'token_expires_in': access_max_age,
    }), 200)
    resp.set_cookie(
        'voxflow_token',
        new_access,
        httponly = True,
        secure   = is_production,
        samesite = 'Lax',
        max_age  = access_max_age,
    )
    return resp


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    access_ttl = int(timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']).total_seconds())

    # Revoga access token (jti adicionado a partir de agora)
    access_token = request.cookies.get('voxflow_token') or (
        request.headers.get('Authorization', '').removeprefix('Bearer ').strip() or None
    )
    if access_token:
        payload = verify_jwt_token(access_token)
        if payload and payload.get('jti'):
            revoke_token(payload['jti'], ttl_seconds=access_ttl)

    # Revoga refresh token
    refresh_token = request.cookies.get('voxflow_refresh')
    if refresh_token:
        payload = verify_jwt_token(refresh_token)
        if payload and payload.get('jti'):
            revoke_refresh_token(payload['jti'])

    resp = make_response(redirect('/login'))
    resp.delete_cookie('voxflow_token')
    resp.delete_cookie('voxflow_refresh', path='/auth/refresh')
    return resp
