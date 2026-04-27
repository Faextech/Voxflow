import logging
import os
from flask import Flask, request
from sqlalchemy import inspect, text

from app.extensions import db, cors, migrate
from config import config as app_config

logger = logging.getLogger(__name__)


def _auto_add_missing_columns(db):
    """
    Adiciona colunas que ainda não existem no banco de dados (SQLite/Postgres).
    Útil para aplicar mudanças sem precisar do flask db upgrade no Railway.
    """
    db_url = str(db.engine.url)

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    pending = []

    if "companies" in tables:
        existing = {col["name"] for col in inspector.get_columns("companies")}
        new_cols = {
            "twilio_api_key":       "VARCHAR(255)",
            "twilio_api_secret":    "VARCHAR(512)",
            "twilio_twiml_app_sid": "VARCHAR(255)",
            "credit_balance":       "NUMERIC(12, 4) DEFAULT 0",
            "cost_per_minute":      "NUMERIC(8, 4) DEFAULT 0.35",
            "twilio_subaccount_sid": "VARCHAR(255)",
            "reg_type":             "VARCHAR(50)",
            "reg_name":             "VARCHAR(255)",
            "reg_tax_id":           "VARCHAR(50)",
            "reg_address":          "TEXT",
            "reg_document_path":    "VARCHAR(512)",
        }
        for col, col_type in new_cols.items():
            if col not in existing:
                pending.append(f"ALTER TABLE companies ADD COLUMN {col} {col_type}")

    if "leads" in tables:
        existing = {col["name"] for col in inspector.get_columns("leads")}
        new_cols = {
            "city":  "VARCHAR(100)",
            "state": "VARCHAR(50)",
        }
        for col, col_type in new_cols.items():
            if col not in existing:
                pending.append(f"ALTER TABLE leads ADD COLUMN {col} {col_type}")

    if "campaigns" in tables:
        existing = {col["name"] for col in inspector.get_columns("campaigns")}
        new_cols = {
            "default_pipeline_id": "INTEGER",
            "default_stage_id": "INTEGER",
        }
        for col, col_type in new_cols.items():
            if col not in existing:
                pending.append(f"ALTER TABLE campaigns ADD COLUMN {col} {col_type}")

    if "deals" in tables:
        existing = {col["name"] for col in inspector.get_columns("deals")}
        if "notes" not in existing:
            pending.append("ALTER TABLE deals ADD COLUMN notes TEXT")

    if pending:
        with db.engine.connect() as conn:
            for stmt in pending:
                conn.execute(text(stmt))
            conn.commit()
        logger.info(f"SQLite auto-migration: {len(pending)} coluna(s) adicionada(s)")


def create_app():
    app = Flask(__name__)

    # carrega config correta conforme FLASK_ENV
    app.config.from_object(app_config)

    flask_env = os.getenv("FLASK_ENV", "development")
    logger.info("[STARTUP] VoxFlow iniciando — env=%s", flask_env.upper())

    # extensões
    db.init_app(app)
    cors.init_app(
        app,
        origins=app.config.get('CORS_ORIGINS', ['http://localhost:5000']),
        supports_credentials=True
    )
    migrate.init_app(app, db)

    # ── WhiteNoise — serve arquivos estáticos sem Nginx (produção) ──────────
    if flask_env == "production":
        try:
            from whitenoise import WhiteNoise
            # Pasta static/ do Flask (app/static e /static na raiz)
            static_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
            if os.path.isdir(static_root):
                app.wsgi_app = WhiteNoise(app.wsgi_app, root=static_root, prefix="static")
                logger.info("[STARTUP] WhiteNoise ativado para arquivos estáticos")
        except ImportError:
            logger.warning("[STARTUP] WhiteNoise não instalado — static files sem cache otimizado")

    # rotas
    from app.routes import register_blueprints
    register_blueprints(app)

    # importa models para o Flask-Migrate enxergar
    with app.app_context():
        from app.models import Company, User, Campaign, Lead, Call, Agent
        from app.models.callback_queue import CallbackQueue
        # CRM models
        from app.models.pipeline import Pipeline, PipelineStage
        from app.models.stage_automation import StageAutomation, AutomationLog
        from app.models.pipeline_transition_rule import PipelineTransitionRule
        from app.models.deal import Deal
        from app.models.deal_activity import DealActivity
        from app.models.deal_task import DealTask
        from app.models.notification import Notification
        from app.models.support import SupportTicket, TicketMessage
        from app.models.billing import CreditTransaction
        from app.models.invite_code import InviteCode
        # Cria tabelas novas; não altera as que já existem
        db.create_all()

        # Auto-migration para colunas faltantes (útil em produção na Railway sem console)
        _auto_add_missing_columns(db)

        # ── Startup cleanup — executa UMA VEZ por inicialização ───────────────
        # Quando o servidor reinicia, AUTO_DIALER_SESSIONS (dict em memória) é
        # apagado. Leads que ficaram em 'dialing' ficam presos para sempre, e
        # campanhas marcadas como 'running' no banco ficam sem sessão ativa.
        # Esta rotina corrige o estado inconsistente automaticamente.
        try:
            from app.models.lead import Lead as _Lead
            from app.models.campaign import Campaign as _Camp

            stuck_leads = _Lead.query.filter(_Lead.status == "dialing").all()
            if stuck_leads:
                for _lead in stuck_leads:
                    _lead.status = "new"
                logger.info(
                    "[STARTUP] %d lead(s) presos em 'dialing' resetados para 'new'",
                    len(stuck_leads),
                )

            # Campanhas 'running' sem sessão em memória → 'paused'
            # (a sessão em memória não existe ainda, então todas estão sem sessão)
            running_camps = _Camp.query.filter_by(status="running").all()
            if running_camps:
                for _camp in running_camps:
                    _camp.status = "paused"
                logger.info(
                    "[STARTUP] %d campanha(s) 'running' sem sessao -> 'paused' (reiniciar pelo discador)",
                    len(running_camps),
                )

            if stuck_leads or running_camps:
                db.session.commit()
        except Exception as _startup_err:
            logger.warning("[STARTUP] cleanup falhou (inofensivo): %s", _startup_err)

        # ── Garante superadmin ────────────────────────────────────────────────
        try:
            _superadmin_email = os.getenv("SUPERADMIN_EMAIL", "allan.consultoriajba@gmail.com").lower()
            _su = User.query.filter_by(email=_superadmin_email).first()
            if _su and _su.role != "superadmin":
                _su.role = "superadmin"
                db.session.commit()
                logger.info("[STARTUP] Usuário %s promovido a superadmin", _superadmin_email)
        except Exception as _su_err:
            logger.warning("[STARTUP] Promoção de superadmin falhou (inofensivo): %s", _su_err)


    @app.route('/health', methods=['GET'])
    def health():
        from datetime import datetime
        return {
            'status': 'ok',
            'message': 'VoxFlow operacional',
            'env': os.getenv('FLASK_ENV', 'development'),
            'timestamp': datetime.utcnow().isoformat(),
        }, 200

    @app.before_request
    def log_request():
        if app.config.get('DEBUG'):
            logger.debug(f'{request.method} {request.path}')

    @app.after_request
    def security_headers(response):
        """Headers de segurança básicos para produção."""
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response

    return app