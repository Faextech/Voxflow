from app import create_app
from app.models.user import User

app = create_app()
with app.app_context():
    u = User.query.first()
    print(f"First user: {u.email}, ID: {u.id}, Company: {u.company_id}")
    
    u2 = User.query.filter_by(email='admin@voxflow.com').first()
    if u2:
        print(f"Admin user: {u2.email}, ID: {u2.id}, Company: {u2.company_id}")
