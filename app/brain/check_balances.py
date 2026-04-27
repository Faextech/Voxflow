import sys
import os
from decimal import Decimal

# Add the app directory to sys.path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models import Company

app = create_app()
with app.app_context():
    companies = Company.query.all()
    print("ID | Name | Balance")
    print("-" * 30)
    for c in companies:
        print(f"{c.id} | {c.name} | {c.credit_balance}")
