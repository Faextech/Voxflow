"""
Socket Service — VoxFlow
Emite eventos em tempo real para o frontend via Flask-SocketIO.
Substitui o polling de 1s do dashboard.

Usa a instância `socketio` de app.extensions (padrão Flask application factory).

Rooms: "company_{company_id}" — cada empresa recebe apenas seus próprios eventos.

Eventos emitidos:
  dialer_status     → status do discador mudou (substitui polling)
  call_update       → chamada criada/atualizada/encerrada
  lead_update       → status do lead mudou
  campaign_update   → campanha pausada/finalizada
  notification      → alerta de sistema (saldo baixo, voicemail alto, etc.)
"""
import logging

logger = logging.getLogger(__name__)


def init_socketio(app):
    """
    Registra handlers de eventos SocketIO no app.
    A instância `socketio` já foi inicializada em extensions.py e
    conectada ao app via socketio.init_app(app) no create_app().
    """
    try:
        from app.extensions import socketio

        @socketio.on("connect")
        def _on_connect():
            logger.debug("[WS] Cliente conectado")

        @socketio.on("disconnect")
        def _on_disconnect():
            logger.debug("[WS] Cliente desconectado")

        @socketio.on("join")
        def _on_join(data):
            """
            Payload: { "company_id": 123, "token": "..." }
            Frontend chama emit("join", ...) logo após conectar.
            Valida JWT antes de entrar na room da empresa.
            """
            from flask_socketio import join_room
            from app.auth import verify_jwt_token
            token = (data or {}).get("token", "")
            payload = verify_jwt_token(token)
            if not payload:
                logger.warning("[WS] join sem token válido — negado")
                return False
            company_id = payload.get("company_id")
            if company_id:
                room = f"company_{company_id}"
                join_room(room)
                logger.info("[WS] user_id=%s entrou na room %s", payload.get("user_id"), room)

        @socketio.on("leave")
        def _on_leave(data):
            from flask_socketio import leave_room
            from app.auth import verify_jwt_token
            # Valida JWT antes de sair — evita que client remova outros da room
            token = (data or {}).get("token", "")
            payload = verify_jwt_token(token)
            if not payload:
                logger.warning("[WS] leave sem token válido — negado")
                return False
            company_id = payload.get("company_id")
            if company_id:
                leave_room(f"company_{company_id}")

        logger.info("[STARTUP] Flask-SocketIO handlers registrados")

    except ImportError as e:
        logger.warning("[WS] flask-socketio não disponível: %s", e)
    except Exception as e:
        logger.error("[WS] Falha ao registrar handlers SocketIO: %s", e)


# ── Emit helpers ──────────────────────────────────────────────────────────────

def _emit_to_company(company_id: int, event: str, data: dict):
    """Emite evento para todos os clientes da empresa. Silencioso se WS não disponível."""
    try:
        from app.extensions import socketio
        from flask import current_app
        room = f"company_{company_id}"
        # Se chamado de thread sem app context, push um context temporário
        try:
            socketio.emit(event, data, to=room)
        except RuntimeError as ctx_err:
            # Thread sem app context — tenta com app context explícito
            try:
                app = socketio.server.environ.get('werkzeug.app') if hasattr(socketio, 'server') else None
                if app:
                    with app.app_context():
                        socketio.emit(event, data, to=room)
                else:
                    logger.debug("[WS] emit %s ignorado — sem app context disponível", event)
                    return
            except Exception:
                logger.debug("[WS] emit %s descartado (thread sem contexto)", event)
                return
        logger.debug("[WS] emit %s → room=%s", event, room)
    except Exception as e:
        logger.warning("[WS] emit falhou (%s): %s", event, e)


def emit_dialer_status(company_id: int, campaign_id: int, session_data: dict):
    """
    Emite status completo do discador.
    Chamado por _save_session() no auto_dialer.py — substitui polling de 1s.
    """
    _emit_to_company(company_id, "dialer_status", {
        "campaign_id": campaign_id,
        "session":     session_data,
    })


def emit_call_update(company_id: int, call_data: dict):
    """Emite atualização de chamada (criada, respondida, encerrada)."""
    _emit_to_company(company_id, "call_update", call_data)


def emit_lead_update(company_id: int, lead_id: int, status: str, extra: dict = None):
    """Emite quando o status de um lead muda."""
    payload = {"lead_id": lead_id, "status": status}
    if extra:
        payload.update(extra)
    _emit_to_company(company_id, "lead_update", payload)


def emit_campaign_update(company_id: int, campaign_id: int, status: str, extra: dict = None):
    """Emite quando o status de uma campanha muda."""
    payload = {"campaign_id": campaign_id, "status": status}
    if extra:
        payload.update(extra)
    _emit_to_company(company_id, "campaign_update", payload)


def emit_notification(company_id: int, level: str, message: str, extra: dict = None):
    """
    Emite notificação de sistema.
    level: 'info' | 'warning' | 'error'
    """
    payload = {"level": level, "message": message}
    if extra:
        payload.update(extra)
    _emit_to_company(company_id, "notification", payload)
