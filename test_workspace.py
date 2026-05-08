from app import create_app
from app.auth import generate_jwt_token
from app.models.user import User

app = create_app()
with app.app_context():
    u = User.query.first()
    token = generate_jwt_token(u.id, u.company_id, u.role)
    print(f"TOKEN={token}")
