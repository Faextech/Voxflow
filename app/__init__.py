import logging
import os
import threading
import time
from flask import Flask, request

from app.extensions import db, cors, migrate, socketio

logger = logging.getLogger(__name__)



def _run_followup_tasks(app):
    """Executa tarefas de follow-up pendentes com scheduled_at <= agora."""
    with app.app_context():
        from datetime import datetime
        from app.models.followup import FollowUpTask
        from app.models.lead import Lead as _Lead

        due = FollowUpTask.query.filter(
            FollowUpTask.status == "pending",
            FollowUpTask.scheduled_at <= datetime.utcnow(),
        ).limit(100).all()

        if not due:
            return

        for task in due:
            try:
                action   = task.action or "email"
                lead     = _Lead.query.get(task.lead_id)
                lead_name = lead.name if lead else f"Lead #{task.lead_id}"

                if action == "email":
                    # Placeholder: log + mark sent (real send requer SMTP configurado)
                    logger.info(
                        "[FOLLOWUP] email → lead=%s template=%s (SMTP não configurado)",
                        task.lead_id, task.template,
                    )
                    task.status      = "sent"
                    task.executed_at = datetime.utcnow()

                elif action == "whatsapp":
                    # Placeholder: log + mark sent (real send requer Twilio Messaging)
                    logger.info(
                        "[FOLLOWUP] whatsapp → lead=%s template=%s (Messaging não configurado)",
                        task.lead_id, task.template,
                    )
                    task.status      = "sent"
                    task.executed_at = datetime.utcnow()

                elif action in ("ligar", "call"):
                    # Marca como pendente manual — operador vê na aba Tarefas
                    task.status = "pending_manual"
                    logger.info("[FOLLOWUP] ligação manual agendada → lead=%s", task.lead_id)

                else:
                    task.status      = "sent"
                    task.executed_at = datetime.utcnow()

            except Exception as _te:
                logger.warning("[FOLLOWUP] Erro ao executar task %s: %s", task.id, _te)
                task.status = "failed"

        db.session.commit()
        logger.info("[FOLLOWUP] %d tarefa(s) processadas", len(due))


def _is_call_active_on_twilio(call_sid: str, company_id: int) -> bool:
    """Verifica via API Twilio se uma chamada ainda está ativa antes de resetar o lead."""
    try:
        from app.models.company import Company as _Comp
        from app.services.twilio_service import TwilioService as _TS
        company = _Comp.query.get(company_id)
        if not company:
            return False
        svc = _TS.from_company(company)
        call = svc.client.calls(call_sid).fetch()
        return call.status in ("queued", "ringing", "in-progress")
    except Exception:
        return False


def _start_periodic_cleanup(app):
    """
    Job em background que roda a cada 5 minutos para:
    - Resetar leads presos em 'dialing' por mais de 10min, verificando se não há
      chamada ativa no Twilio antes de resetar (evita BUG-C06)
    - Executar tarefas de follow-up pendentes
    """
    def _run():
        while True:
            time.sleep(300)  # 5 minutos
            try:
                with app.app_context():
                    from datetime import datetime, timedelta
                    from app.models.lead import Lead as _Lead
                    from app.models.call import Call as _Call
                    cutoff = datetime.utcnow() - timedelta(minutes=10)
                    stuck = _Lead.query.filter(
                        _Lead.status == "dialing",
                        _Lead.updated_at < cutoff,
                    ).all()
                    reset_count = 0
                    for _lead in stuck:
                        # Verifica se existe chamada ativa para este lead no Twilio
                        latest_call = (
                            _Call.query
                            .filter_by(lead_id=_lead.id)
                            .order_by(_Call.created_at.desc())
                            .first()
                        )
                        if latest_call and latest_call.call_sid:
                            if _is_call_active_on_twilio(latest_call.call_sid, _lead.company_id):
                                logger.info(
                                    "[CLEANUP] Lead %s ainda tem chamada ativa (%s) — ignorando reset",
                                    _lead.id, latest_call.call_sid,
                                )
                                continue
                        _lead.status = "new"
                        reset_count += 1
                    if reset_count:
                        db.session.commit()
                        logger.info("[CLEANUP] %d lead(s) presos em 'dialing' resetados", reset_count)
            except Exception as e:
                logger.warning("[CLEANUP] Erro no job periódico: %s", e)

            try:
                _run_followup_tasks(app)
            except Exception as e:
                logger.warning("[FOLLOWUP] Erro no job periódico: %s", e)

    t = threading.Thread(target=_run, daemon=True, name="PeriodicCleanup")
    t.start()
    logger.info("[STARTUP] Job de cleanup + follow-up periódico iniciado (5min)")


def create_app():
    app = Flask(__name__)

    from config import config as app_config
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

    # ── Flask-SocketIO (WebSocket real-time) ────────────────────────────
    # 1. Vincula a instância global ao app (configura async_mode, cors, etc.)
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode="threading",   # compatível com Gunicorn workers=1 + threads
        logger=False,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25,
    )
    # 2. Registra handlers de eventos (join, leave, connect, disconnect)
    from app.services.socket_service import init_socketio
    init_socketio(app)


    # ── WhiteNoise — serve arquivos estáticos sem Nginx (produção) ──────────
    if flask_env == "production":
        try:
            from whitenoise import WhiteNoise
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
        from app.models.audit_log import AuditLog
        from app.models.dnc import DNCEntry
        from app.models.followup import FollowUpSequence, FollowUpTask
        db.create_all()

        # ── Startup cleanup ───────────────────────────────────────────────────
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

            running_camps = _Camp.query.filter_by(status="running").all()
            if running_camps:
                for _camp in running_camps:
                    _camp.status = "paused"
                logger.info(
                    "[STARTUP] %d campanha(s) 'running' sem sessão -> 'paused'",
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

    # ── Job periódico de cleanup (reseta leads presos após SIGKILL) ──────────
    _start_periodic_cleanup(app)

    @app.route('/health', methods=['GET'])
    def health():
        from datetime import datetime
        from app.services import redis_service
        return {
            'status': 'ok',
            'message': 'VoxFlow operacional',
            'env': os.getenv('FLASK_ENV', 'development'),
            'redis': 'connected' if redis_service.is_available() else 'fallback_memory',
            'timestamp': datetime.utcnow().isoformat(),
        }, 200

    @app.before_request
    def csrf_protect():
        """
        Valida CSRF token para todas as rotas de API que modificam estado.
        Exceções: Twilio webhooks (sem cookies) e endpoints de auth.
        Bypass automático para requests com Authorization: Bearer (clientes API).
        """
        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return

        path = request.path
        # Twilio webhooks não enviam cookies
        if path.startswith('/api/twilio/'):
            return
        # Auth endpoints (login usa rate-limit próprio; refresh/logout são safe)
        if path.startswith('/auth/'):
            return
        # Clients API com Bearer token explícito estão autenticados por token
        if request.headers.get('Authorization', '').startswith('Bearer '):
            return
        # Apenas rotas de API precisam de CSRF — páginas HTML não são afetadas
        if not path.startswith('/api/'):
            return

        from app.auth import generate_csrf_token as _gen  # noqa — import for secrets.compare_digest
        import secrets
        cookie_token = request.cookies.get('voxflow_csrf', '')
        header_token = request.headers.get('X-CSRF-Token', '')

        if not cookie_token or not header_token:
            logger.warning("[CSRF] Token ausente path=%s ip=%s", path, request.remote_addr)
            from flask import jsonify as _jsonify
            return _jsonify({'error': 'CSRF token ausente'}), 403

        if not secrets.compare_digest(cookie_token, header_token):
            logger.warning("[CSRF] Token inválido path=%s ip=%s", path, request.remote_addr)
            from flask import jsonify as _jsonify
            return _jsonify({'error': 'CSRF token inválido'}), 403

    @app.before_request
    def log_request():
        if app.config.get('DEBUG'):
            logger.debug(f'{request.method} {request.path}')

    @app.after_request
    def security_headers(response):
        """Headers de segurança completos — CSP, HSTS, anti-clickjacking."""
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('X-XSS-Protection', '1; mode=block')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(self), geolocation=()')

        # Content Security Policy — permite Twilio SDK, Tailwind, Lucide, WebSockets
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
                "https://cdn.tailwindcss.com https://unpkg.com "
                "https://media.twiliocdn.com https://sdk.twilio.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
                "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' https://*.twilio.com wss://*.twilio.com "
                "ws: wss: https://eventgw.twilio.com https://chunderw-vpc-gll.twilio.com; "
            "media-src 'self' blob:; "
            "worker-src 'self' blob:; "
            "frame-ancestors 'self';"
        )
        response.headers.setdefault('Content-Security-Policy', csp)

        if flask_env == "production":
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains'
            )

        return response

    # ── CLI commands ─────────────────────────────────────────────────────────
    import click

    @app.cli.command("create-superadmin")
    @click.argument("email")
    @click.password_option(prompt="Password", confirmation_prompt=True)
    def create_superadmin(email, password):
        """Cria ou promove um usuário a superadmin. Uso: flask create-superadmin EMAIL"""
        from werkzeug.security import generate_password_hash
        from app.models.company import Company

        with app.app_context():
            email = email.strip().lower()
            user = User.query.filter_by(email=email).first()
            if user:
                user.role   = "superadmin"
                user.status = "active"
                if password:
                    user.password_hash = generate_password_hash(password, method="pbkdf2:sha256")
                db.session.commit()
                click.echo(f"[OK] Usuário {email} promovido a superadmin.")
            else:
                # Cria empresa + usuário superadmin
                company = Company(name="Super Admin", email=email)
                db.session.add(company)
                db.session.flush()
                new_user = User(
                    company_id    = company.id,
                    name          = "Super Admin",
                    email         = email,
                    password_hash = generate_password_hash(password, method="pbkdf2:sha256"),
                    role          = "superadmin",
                    status        = "active",
                )
                db.session.add(new_user)
                db.session.commit()
                click.echo(f"[OK] Superadmin {email} criado (company_id={company.id}).")

    @app.cli.command("list-superadmins")
    def list_superadmins():
        """Lista todos os usuários com role superadmin."""
        with app.app_context():
            admins = User.query.filter_by(role="superadmin").all()
            if not admins:
                click.echo("Nenhum superadmin encontrado.")
                return
            for u in admins:
                click.echo(f"  id={u.id}  email={u.email}  company_id={u.company_id}  status={u.status}")

    @app.cli.command("rotate-fernet-key")
    @click.option("--dry-run", is_flag=True, default=False,
                  help="Simula a rotação sem gravar no banco.")
    def rotate_fernet_key(dry_run):
        """
        [SEC-07] Rotação segura da chave Fernet.

        Gera uma nova FERNET_KEY, re-encripta todos os segredos Twilio de todas
        as empresas com a nova chave e imprime a nova chave para atualizar o .env.

        Uso:
          flask rotate-fernet-key           # aplica
          flask rotate-fernet-key --dry-run # simula sem gravar
        """
        from cryptography.fernet import Fernet, MultiFernet
        from app.models.company import Company

        old_key_str = (os.getenv("FERNET_KEY") or "").strip()
        if not old_key_str:
            click.echo("[ERRO] FERNET_KEY não configurada no .env. Abortando.", err=True)
            raise SystemExit(1)

        new_key = Fernet.generate_key()
        old_f   = Fernet(old_key_str.encode())
        new_f   = Fernet(new_key)
        # MultiFernet tenta a chave nova primeiro; se falhar usa a velha (para registros já migrados)
        multi   = MultiFernet([new_f, old_f])

        ENCRYPTED_FIELDS = ["twilio_auth_token", "twilio_api_secret"]

        with app.app_context():
            companies = Company.query.all()
            rotated   = 0
            skipped   = 0

            for company in companies:
                changed = False
                for field in ENCRYPTED_FIELDS:
                    ciphertext = getattr(company, field, None)
                    if not ciphertext:
                        continue
                    try:
                        # Descriptografa com chave antiga
                        plaintext = old_f.decrypt(ciphertext.encode()).decode()
                        # Re-encripta com chave nova
                        new_cipher = new_f.encrypt(plaintext.encode()).decode()
                        if not dry_run:
                            setattr(company, field, new_cipher)
                        changed = True
                    except Exception as e:
                        click.echo(f"  [WARN] company_id={company.id} campo={field}: {e}")
                        skipped += 1

                if changed:
                    rotated += 1

            if not dry_run:
                db.session.commit()
                click.echo(f"\n[OK] {rotated} empresas re-encriptadas. {skipped} campos ignorados.")
                click.echo("\n" + "=" * 60)
                click.echo("NOVA FERNET_KEY (atualize seu .env AGORA):")
                click.echo(f"  FERNET_KEY={new_key.decode()}")
                click.echo("=" * 60 + "\n")
                click.echo("[AVISO] Reinicie o servidor após atualizar o .env.")
            else:
                click.echo(f"\n[DRY-RUN] {rotated} empresas seriam re-encriptadas. {skipped} campos ignorados.")
                click.echo(f"[DRY-RUN] Nova chave seria: {new_key.decode()}")

    return app

