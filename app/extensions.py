from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate
from flask_socketio import SocketIO

# Instâncias globais
db = SQLAlchemy()
cors = CORS()
migrate = Migrate()
socketio = SocketIO()