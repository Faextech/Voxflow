import sys
import os

# Adiciona o diretório atual ao sys.path para que o script possa importar o 'app'
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

def reset_password(email, new_password):
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"Erro: Usuário '{email}' não encontrado.")
            return

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        print(f"Sucesso: Senha do usuário '{email}' foi resetada.")

if __name__ == "__main__":
    email_to_reset = "operador_6a11a0@teste.com"
    temp_password = "NexDial@2026"
    
    reset_password(email_to_reset, temp_password)
