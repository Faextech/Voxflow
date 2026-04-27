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
    master = Company.query.get(1)
    client = Company.query.get(3)
    
    if master and client:
        print(f"Fixing balances...")
        print(f"Master (ID 1): {master.credit_balance} -> 32.6618")
        print(f"Client (ID 3): {client.credit_balance} (stays 10.00)")
        
        master.credit_balance = Decimal("32.6618")
        db.session.commit()
        print("Done.")
    else:
        print("Master or Client not found.")
