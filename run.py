"""
Ponto de entrada da aplicação NexDial.

Modos de execução:
  Desenvolvimento:  python run.py
  Produção (local): FLASK_ENV=production python run.py
  Produção (Railway/VPS): gunicorn "run:create_app()" -c gunicorn.conf.py
"""

import logging
import os
import sys

from dotenv import load_dotenv

# Carrega variáveis de ambiente (ignorado em produção onde as vars vêm do painel)
load_dotenv()

flask_env = os.getenv("FLASK_ENV", "development")

# ─── Logging ──────────────────────────────────────────────────────────────────
# Produção: apenas WARNING+ para stdout (Railway/VPS capturam stdout)
# Desenvolvimento: DEBUG para stdout + arquivo local
log_level  = logging.DEBUG if flask_env == "development" else logging.INFO
log_format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"

handlers = [logging.StreamHandler(sys.stdout)]
if flask_env == "development":
    handlers.append(logging.FileHandler("app.log", encoding="utf-8"))

logging.basicConfig(level=log_level, format=log_format, handlers=handlers)
logger = logging.getLogger(__name__)

# ─── Importa factory ─────────────────────────────────────────────────────────
from app import create_app as app_factory  # noqa: E402


def create_app():
    """
    Factory function chamada pelo Gunicorn:
      gunicorn "run:create_app()"
    """
    return app_factory()


# ─── Execução direta (python run.py) ─────────────────────────────────────────
if __name__ == "__main__":
    if flask_env not in ("development", "production", "testing"):
        logger.error("FLASK_ENV inválido: %s — use: development | production | testing", flask_env)
        sys.exit(1)

    app = create_app()
    port = int(os.getenv("PORT", 5000))

    # Obtém instância SocketIO para suportar WebSocket
    try:
        from app.extensions import socketio as sio
        _runner = sio.run
    except Exception:
        _runner = None

    if flask_env == "development":
        logger.info("NexDial iniciando em modo DESENVOLVIMENTO — http://localhost:%d", port)
        logger.info("Pressione CTRL+C para parar")
        if _runner:
            _runner(
                app,
                host="0.0.0.0",
                port=port,
                debug=True,
                use_reloader=False,  # SocketIO e reloader não combinam bem
                allow_unsafe_werkzeug=True,
            )
        else:
            app.run(host="0.0.0.0", port=port, debug=True, use_reloader=True)
    else:
        # Em produção use Gunicorn (Procfile / Railway).
        # Este bloco é fallback caso `python run.py` seja chamado em produção.
        logger.warning(
            "Executando Flask built-in server em produção — use Gunicorn para performance."
        )
        if _runner:
            _runner(app, host="0.0.0.0", port=port, debug=False)
        else:
            app.run(host="0.0.0.0", port=port, debug=False)