import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, make_response, redirect, request, current_app, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import Company, User
from app.models.agent import Agent
from app.models.pipeline import Pipeline, PipelineStage
from app.models.invite_code import InviteCode
from app.auth import generate_jwt_token

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    name         = data.get('name', 'Administrador')
    email        = (data.get('email') or '').strip().lower()
    password     = data.get('password')
    company_name = data.get('company_name', 'Minha Empresa')
    invite_code  = (data.get('invite_code') or '').strip()

    if not email or not password:
        return jsonify({'error': 'Email e senha são obrigatórios'}), 400

    if not invite_code:
        return jsonify({'error': 'Código de convite é obrigatório'}), 400

    invite = InviteCode.query.filter_by(code=invite_code).first()
    if not invite or not invite.is_valid():
        return jsonify({'error': 'Código de convite inválido ou já utilizado'}), 403

    # Verifica se email já está em uso (email é unique na tabela users)
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email já cadastrado'}), 400

    company = Company(name=company_name, email=email)
    db.session.add(company)
    db.session.flush()  # gera company.id sem commitar

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

    # ── Pipeline padrão para novas empresas ──────────────────────────────────
    _pipeline = Pipeline(
        company_id = company.id,
        name       = "Comercial",
        description= "Pipeline padrão de vendas criado automaticamente",
        color      = "#6366f1",
        is_default = True,
        position   = 0,
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
    # ─────────────────────────────────────────────────────────────────────────

    # Marca convite como utilizado
    invite.used = True
    invite.used_by_company_id = company.id
    invite.used_at = datetime.utcnow()
    db.session.commit()

    # Cria subconta Twilio automaticamente (falha silenciosa — admin cria manualmente se necessário)
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
    data = request.get_json() or {}

    email    = (data.get('email') or '').strip().lower()
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email e senha são obrigatórios'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        # Mesma mensagem para não revelar se o email existe
        return jsonify({'error': 'Credenciais inválidas'}), 401

    if not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Credenciais inválidas'}), 401

    if user.status != 'active':
        return jsonify({'error': 'Conta inativa. Contate o suporte.'}), 403

    token = generate_jwt_token(user.id, user.company_id, user.role)

    # agent_id para o webphone (via agent_profile)
    agent_id = user.agent_profile.id if user.agent_profile else None

    # Em produção (DEBUG=False), o cookie só trafega em HTTPS
    is_production = not current_app.config.get('DEBUG', False)
    cookie_max_age = int(
        timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']).total_seconds()
    )

    resp = make_response(jsonify({
        'message':    'Login realizado com sucesso',
        'token':      token,
        'user_id':    user.id,
        'company_id': user.company_id,
        'agent_id':   agent_id,
        'email':      user.email,
        'name':       user.name,
        'role':       user.role,
    }), 200)

    # Cookie HttpOnly: o browser envia automaticamente; JS não consegue ler
    resp.set_cookie(
        'voxflow_token',
        token,
        httponly  = True,
        secure    = is_production,   # False em dev (HTTP), True em prod (HTTPS)
        samesite  = 'Lax',           # protege contra CSRF em navegação normal
        max_age   = cookie_max_age,
    )

    return resp


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    resp = make_response(redirect(url_for('pages.login_page')))
    resp.delete_cookie('voxflow_token')
    return resp
