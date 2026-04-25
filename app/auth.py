"""
Módulo de Autenticação e Segurança
Gerencia: JWT, decoradores de autenticação, hashing de senha, rate limiting
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from time import time

import bcrypt
import jwt
from flask import g, jsonify, request, current_app

from app.models import User

logger = logging.getLogger(__name__)


# ========== HASHING DE SENHA ==========

def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Senha deve ter no mínimo 8 caracteres")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception as e:
        logger.error(f"Erro ao verificar senha: {str(e)}")
        return False


# ========== JWT TOKENS ==========

def generate_jwt_token(user_id: int, company_id: int, role: str = 'agent') -> str:
    """
    Gera token JWT com user_id, company_id e role no payload.
    role é incluído para que os decoradores não precisem consultar o banco a cada request.
    """
    payload = {
        'user_id': user_id,
        'company_id': company_id,
        'role': role,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']),
    }
    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm=current_app.config['JWT_ALGORITHM'],
    )


def verify_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']],
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Token expirado")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token inválido: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Erro ao verificar token: {str(e)}")
        return None


# ========== DECORADORES PRINCIPAIS ==========

def require_auth(f):
    """
    Exige JWT válido na rota.

    Lê o token de (em ordem de prioridade):
      1. Header  →  Authorization: Bearer <token>
      2. Cookie  →  nexdial_token  (HttpOnly, definido no login)

    Popula flask.g com:
      g.user_id    – int
      g.company_id – int  (usado para filtrar queries por tenant)
      g.user_role  – str  ('admin' | 'agent')
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()

        if not token:
            token = request.cookies.get('nexdial_token')

        # Aceita _token como query param (para downloads via window.location)
        if not token:
            token = request.args.get('_token')

        if not token:
            return jsonify({'error': 'Token obrigatório'}), 401

        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Token expirado ou inválido'}), 401

        user = User.query.get(payload.get('user_id'))
        if not user or user.status != 'active':
            return jsonify({'error': 'Usuário inválido ou inativo'}), 401

        # Garante que o token pertence ao tenant correto
        if user.company_id != payload.get('company_id'):
            return jsonify({'error': 'Token inválido'}), 401

        g.user_id    = user.id
        g.company_id = user.company_id
        g.user_role  = user.role

        return f(*args, **kwargs)

    return decorated


def require_role(*roles):
    """
    Decorator factory que restringe acesso por role.
    DEVE ser empilhado APÓS @require_auth (depende de g.user_role).

    Uso:
        @require_auth
        @require_role('admin')
        def rota_admin(): ...

        @require_auth
        @require_role('admin', 'agent')
        def rota_compartilhada(): ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            current_role = getattr(g, 'user_role', 'none')
            if current_role not in roles:
                logger.error(f"Acesso negado. Role required: {roles}, actual: {current_role}, user_id: {getattr(g, 'user_id', 'none')}")
                return jsonify({
                    'error': f"Acesso restrito a: {', '.join(roles)}"
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ========== DECORADORES LEGADOS (mantidos para não quebrar código existente) ==========

def token_required(f):
    """Legado — use @require_auth para novas rotas."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(' ')[1]
            except IndexError:
                return jsonify({'error': 'Token inválido no header'}), 401

        if not token:
            return jsonify({'error': 'Token obrigatório'}), 401

        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Token expirado ou inválido'}), 401

        user = User.query.get(payload.get('user_id'))
        if not user or user.status != 'active':
            return jsonify({'error': 'Usuário inválido ou inativo'}), 401

        request.user_id    = payload.get('user_id')
        request.company_id = payload.get('company_id')
        request.user       = user
        request.token      = token

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Legado — use @require_role('admin') para novas rotas."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, 'user') or request.user.role != 'admin':
            return jsonify({'error': 'Acesso restrito a administradores'}), 403
        return f(*args, **kwargs)
    return decorated


# ========== AUDITORIA (log apenas — sem tabela AuditLog por ora) ==========

def log_audit(action: str, resource_type: str = None, resource_id: int = None,
              changes: dict = None, status: str = 'success', error_message: str = None):
    user_id    = getattr(g, 'user_id',    None) or getattr(request, 'user_id',    None)
    company_id = getattr(g, 'company_id', None) or getattr(request, 'company_id', None)
    logger.info(
        'AUDIT action=%s user=%s company=%s resource=%s#%s status=%s error=%s',
        action, user_id, company_id, resource_type, resource_id, status, error_message,
    )


# ========== VALIDAÇÕES ==========

def validate_email(email: str) -> bool:
    import re
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


def validate_password(password: str) -> tuple:
    if len(password) < 8:
        return False, "Senha deve ter no mínimo 8 caracteres"
    if not any(c.isupper() for c in password):
        return False, "Senha deve conter pelo menos uma letra maiúscula"
    if not any(c.isdigit() for c in password):
        return False, "Senha deve conter pelo menos um número"
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        return False, "Senha deve conter pelo menos um caractere especial"
    return True, "Senha válida"


def validate_cnpj(cnpj: str) -> bool:
    import re
    return bool(re.match(r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$', cnpj))


# ========== RATE LIMITING SIMPLES (in-memory — suficiente para login) ==========

_rate_limit_data = defaultdict(list)


def check_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
    now = time()
    _rate_limit_data[key] = [
        ts for ts in _rate_limit_data[key] if now - ts < window_seconds
    ]
    if len(_rate_limit_data[key]) >= max_attempts:
        return False
    _rate_limit_data[key].append(now)
    return True
