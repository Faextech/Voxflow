"""
Configurações da aplicação NexDial
Suporta múltiplos ambientes: development, production, testing
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()


class Config:
    """Configurações base para todos os ambientes"""

    # ========== FLASK ==========
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY or len(SECRET_KEY) < 32:
        raise ValueError(
            "ERRO: SECRET_KEY nao esta definida ou e muito curta no .env\n"
            "Gere uma com: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # ========== BANCO DE DADOS ==========
    database_url = os.getenv('DATABASE_URL', 'sqlite:///nexdial.db')
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite não suporta pool_size/pool_recycle — só aplicar para PostgreSQL
    if database_url.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'echo': False,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 10,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
            'echo': False,
        }

    # ========== SEGURANÇA - COOKIES ==========
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_NAME = 'nexdial_session'

    # ========== SEGURANÇA - HEADERS ==========
    PREFERRED_URL_SCHEME = 'https'
    JSON_SORT_KEYS = False

    # ========== REDIS ==========
    REDIS_URL = os.getenv('REDIS_URL', '')

    # ========== JWT (JSON Web Tokens) ==========
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', '4'))   # access token: 4h
    JWT_REFRESH_EXPIRATION_DAYS = int(os.getenv('JWT_REFRESH_DAYS', '30'))  # refresh: 30 dias

    # ========== CORS (Cross-Origin Resource Sharing) ==========
    CORS_ORIGINS = os.getenv(
        'CORS_ORIGINS',
        'https://web-production-c66e0.up.railway.app,http://localhost:5000,http://localhost:3000'
    ).split(',')

    # ========== TWILIO ==========
    TWILIO_ACCOUNT_SID  = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN   = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    TWILIO_NUMBER       = TWILIO_PHONE_NUMBER  # alias legado

    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        import sys
        print("AVISO: Credenciais Twilio incompletas. Algumas features nao funcionarao.", file=sys.stderr)

    # ========== URLs ==========
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

    # ========== LOGGING ==========
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'nexdial.log'

    # ========== RATE LIMITING ==========
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "100 per hour"

    # ========== LIMITES DA APLICAÇÃO ==========
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    JSON_MAX_SIZE = 1024 * 1024

    # ========== PAGINAÇÃO ==========
    ITEMS_PER_PAGE = 20
    MAX_ITEMS_PER_PAGE = 100

    # ========== TIMEOUTS ==========
    REQUEST_TIMEOUT = 30
    TWILIO_TIMEOUT = 10


class DevelopmentConfig(Config):
    """Configurações para DESENVOLVIMENTO"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    PREFERRED_URL_SCHEME = 'http'
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Configurações para PRODUÇÃO"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    """Configurações para TESTES"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    DEBUG = True


# ========== SELETOR DE CONFIGURAÇÃO ==========
config_env = os.getenv('FLASK_ENV', 'development')

config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

if config_env not in config_map:
    raise ValueError(
        f"FLASK_ENV '{config_env}' inválido. Use: development, production ou testing"
    )

config = config_map[config_env]