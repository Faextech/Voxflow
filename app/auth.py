"""
Módulo de Autenticação e Segurança
Gerencia: JWT, decoradores de autenticação, hashing de senha, rate limiting
"""

import logging
import secrets
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
    Gera access token JWT (curta duração: 4h por padrão).
    Inclui jti para possibilitar revogação imediata no logout.
    """
    jti = secrets.token_urlsafe(16)
    payload = {
        'user_id': user_id,
        'company_id': company_id,
        'role': role,
        'type': 'access',
        'jti': jti,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']),
    }
    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm=current_app.config['JWT_ALGORITHM'],
    )


def generate_refresh_token(user_id: int, company_id: int, role: str = 'agent') -> str:
    """
    Gera refresh token de longa duração (30 dias).
    Inclui jti único para possibilitar revogação pontual.
    """
    jti = secrets.token_urlsafe(32)
    payload = {
        'user_id': user_id,
        'company_id': company_id,
        'role': role,
        'type': 'refresh',
        'jti': jti,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=current_app.config['JWT_REFRESH_EXPIRATION_DAYS']),
    }
    token = jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm=current_app.config['JWT_ALGORITHM'],
    )
    # Armazena jti no Redis para permitir revogação
    try:
        from app.services import redis_service
        ttl = current_app.config['JWT_REFRESH_EXPIRATION_DAYS'] * 86400
        redis_service.set(f"refresh_jti:{jti}", str(user_id), ex=ttl)
    except Exception as e:
        logger.warning("[AUTH] Não foi possível salvar refresh jti no Redis: %s", e)
    return token


def generate_2fa_challenge_token(user_id: int) -> str:
    """
    Gera um token temporário de 5 minutos para o desafio 2FA.
    Emitido quando as credenciais são válidas mas o 2FA está ativado.
    O frontend usa esse token para chamar /auth/login/2fa com o código TOTP.
    """
    payload = {
        'user_id': user_id,
        'type':    '2fa_challenge',
        'iat':     datetime.utcnow(),
        'exp':     datetime.utcnow() + timedelta(minutes=5),
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


def is_token_revoked(jti: str) -> bool:
    """Verifica se o token foi revogado (blacklist no Redis)."""
    try:
        from app.services import redis_service
        return redis_service.exists(f"revoked_token:{jti}")
    except Exception:
        return False


def revoke_token(jti: str, ttl_seconds: int = 3600):
    """Adiciona token à blacklist com TTL."""
    try:
        from app.services import redis_service
        redis_service.set(f"revoked_token:{jti}", "1", ex=ttl_seconds)
    except Exception as e:
        logger.warning("[AUTH] Não foi possível revogar token: %s", e)


def revoke_refresh_token(jti: str):
    """Remove refresh token válido (logout)."""
    try:
        from app.services import redis_service
        redis_service.delete(f"refresh_jti:{jti}")
    except Exception as e:
        logger.warning("[AUTH] Não foi possível revogar refresh token: %s", e)


# ========== DECORADORES PRINCIPAIS ==========

def require_auth(f):
    """
    Exige JWT válido na rota.

    Lê o token de (em ordem de prioridade):
      1. Header  →  Authorization: Bearer <token>
      2. Cookie  →  voxflow_token  (HttpOnly, definido no login)
      3. Query   →  _token (para downloads via window.location)

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
            token = request.cookies.get('voxflow_token')

        if not token:
            token = request.args.get('_token')

        if not token:
            logger.warning("[AUTH DEBUG] Token obrigatorio ausente. Headers: %s, Cookies: %s", request.headers.get('Authorization'), request.cookies.get('voxflow_token'))
            return jsonify({'error': 'Token obrigatório'}), 401

        payload = verify_jwt_token(token)
        if not payload:
            logger.warning("[AUTH DEBUG] Token expirado ou invalido: %s", token)
            return jsonify({'error': 'Token expirado ou inválido'}), 401

        # Rejeita refresh tokens usados como access tokens
        if payload.get('type') == 'refresh':
            logger.warning("[AUTH DEBUG] Tentativa de usar refresh token como access token")
            return jsonify({'error': 'Use o access token, não o refresh token'}), 401

        # Verifica blacklist se tiver jti
        jti = payload.get('jti')
        if jti and is_token_revoked(jti):
            logger.warning("[AUTH DEBUG] Token revogado: %s", jti)
            return jsonify({'error': 'Token revogado'}), 401

        user = User.query.get(payload.get('user_id'))
        if not user or user.status != 'active':
            logger.warning("[AUTH DEBUG] Usuario invalido ou inativo: %s", payload.get('user_id'))
            return jsonify({'error': 'Usuário inválido ou inativo'}), 401

        if user.company_id != payload.get('company_id'):
            logger.warning("[AUTH DEBUG] Company ID mismatch: user=%s, payload=%s", user.company_id, payload.get('company_id'))
            return jsonify({'error': 'Token inválido'}), 401

        g.user_id    = user.id
        g.company_id = user.company_id
        g.user_role  = user.role
        g.user_email = user.email

        return f(*args, **kwargs)

    return decorated


def require_role(*roles):
    """
    Decorator factory que restringe acesso por role.
    DEVE ser empilhado APÓS @require_auth (depende de g.user_role).
    superadmin tem acesso a tudo que admin tem.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            current_role = getattr(g, 'user_role', 'none')
            effective_roles = set(roles)
            if 'admin' in effective_roles:
                effective_roles.add('superadmin')
            if current_role not in effective_roles:
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


# ========== AUDITORIA ==========

def log_audit(action: str, resource_type: str = None, resource_id: int = None,
              changes: dict = None, status: str = 'success', error_message: str = None):
    """
    Persiste uma entrada no AuditLog e emite log estruturado.
    Silencioso em caso de erro para não quebrar a rota auditada.
    """
    user_id    = getattr(g, 'user_id',    None) or getattr(request, 'user_id',    None)
    company_id = getattr(g, 'company_id', None) or getattr(request, 'company_id', None)
    user_email = getattr(g, 'user_email', None)
    ip         = request.remote_addr if request else None

    logger.info(
        'AUDIT action=%s user=%s company=%s resource=%s#%s status=%s error=%s',
        action, user_id, company_id, resource_type, resource_id, status, error_message,
    )

    try:
        from app.models.audit_log import AuditLog
        from app.extensions import db
        entry = AuditLog(
            user_id       = user_id,
            company_id    = company_id,
            user_email    = user_email,
            ip_address    = ip,
            action        = action,
            resource_type = resource_type,
            resource_id   = resource_id,
            changes       = changes,
            status        = status,
            error         = error_message,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as _e:
        logger.warning("[AUDIT] Falha ao persistir entrada: %s", _e)
        try:
            from app.extensions import db as _db
            _db.session.rollback()
        except Exception:
            pass


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


# ========== CSRF — Double-submit cookie pattern ==========

def generate_csrf_token() -> str:
    """Gera token CSRF aleatório (32 bytes = 43 chars base64url)."""
    return secrets.token_urlsafe(32)


def require_csrf(f):
    """
    Valida CSRF token em rotas que modificam estado.
    Lê X-CSRF-Token header e compara com voxflow_csrf cookie.
    Bypass: requests com Authorization Bearer (API externa autenticada por token).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Bypass para clientes com Bearer token explícito (chamadas de API)
        if request.headers.get('Authorization', '').startswith('Bearer '):
            return f(*args, **kwargs)

        cookie_token  = request.cookies.get('voxflow_csrf', '')
        header_token  = request.headers.get('X-CSRF-Token', '')

        if not cookie_token or not header_token:
            logger.warning("[CSRF] Token ausente — cookie=%s header=%s path=%s",
                           bool(cookie_token), bool(header_token), request.path)
            return jsonify({'error': 'CSRF token ausente'}), 403

        if not secrets.compare_digest(cookie_token, header_token):
            logger.warning("[CSRF] Token inválido path=%s ip=%s", request.path, request.remote_addr)
            return jsonify({'error': 'CSRF token inválido'}), 403

        return f(*args, **kwargs)
    return decorated


# ========== RATE LIMITING — Redis com fallback in-memory ==========

def rate_limit(max_calls: int, window_seconds: int = 60, key_prefix: str = ""):
    """
    Decorator de rate limiting por IP + rota.
    Retorna 429 se o limite for excedido.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            key = f"{key_prefix or f.__name__}:{ip}"
            if not check_rate_limit(key, max_attempts=max_calls, window_seconds=window_seconds):
                logger.warning("[RATE_LIMIT] Bloqueado: key=%s", key)
                return jsonify({"error": "Muitas requisições. Aguarde e tente novamente."}), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Fallback in-memory (usado quando Redis não disponível)
from collections import defaultdict
_rate_limit_data = defaultdict(list)


def check_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
    """
    Verifica rate limit. Usa Redis quando disponível (persiste entre restarts).
    Fallback para in-memory quando Redis não está configurado.
    Returns True se permitido, False se bloqueado.
    """
    try:
        from app.services import redis_service
        redis_key = f"rate_limit:{key}"
        count = redis_service.incr(redis_key, ex=window_seconds)
        if count == 1:
            redis_service.expire(redis_key, window_seconds)
        return count <= max_attempts
    except Exception as e:
        logger.warning("[RATE_LIMIT] Redis falhou: %s — usando fallback in-memory", e)

    # Fallback in-memory
    now = time()
    _rate_limit_data[key] = [
        ts for ts in _rate_limit_data[key] if now - ts < window_seconds
    ]
    if len(_rate_limit_data[key]) >= max_attempts:
        return False
    _rate_limit_data[key].append(now)
    return True
