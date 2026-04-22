import sys
import os

# Add current dir to path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models.lead import Lead
from app.models.campaign import Campaign

app = create_app()

with app.app_context():
    print("--- CAMPANHAS ---")
    campaigns = Campaign.query.all()
    for c in campaigns:
        leads_total = Lead.query.filter_by(campaign_id=c.id).count()
        leads_new = Lead.query.filter(
            Lead.campaign_id == c.id,
            Lead.status.in_(["new", "novo"])
        ).count()
        print(f"ID {c.id} | Name: {c.name} | Status: {c.status} | Total Leads: {leads_total} | New Leads: {leads_new}")
        
    print("\n--- AMOSTRA DE LEADS (Ultimos 10) ---")
    leads = Lead.query.order_by(Lead.id.desc()).limit(10).all()
    for l in leads:
        print(f"ID {l.id} | Name: {l.name} | Status: '{l.status}' | Campaign: {l.campaign_id} | Phone1: '{l.numero_1}'")
