"""
Ponto de entrada da aplicação NexDial
Execute com: python run.py
"""

import os
import logging
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

from app import create_app as app_factory


def create_app():
    """Factory function para criar a aplicação Flask"""
    return app_factory()


if __name__ == '__main__':
    flask_env = os.getenv('FLASK_ENV', 'development')

    if flask_env not in ['development', 'production', 'testing']:
        logger.error(f"FLASK_ENV inválido: {flask_env}")
        raise SystemExit(1)

    logger.info(f"Iniciando NexDial em modo: {flask_env.upper()}")

    app = create_app()

    if flask_env == 'development':
        logger.info("Servidor rodando em http://localhost:5000")
        logger.info("Pressione CTRL+C para parar")
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=True
        )
    else:
        logger.info("Executando em produção")
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False
        )