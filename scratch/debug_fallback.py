from app import create_app
from app.extensions import db
from app.models.call import Call
from app.models.lead import Lead

app = create_app()
with app.app_context():
    # Encontrar as calls mais novas da campanha 7
    calls = Call.query.filter_by(campaign_id=7).order_by(Call.created_at.desc()).limit(5).all()
    print("Últimas Calls da Campanha 7:")
    for c in calls:
        print(f"Call ID: {c.id} | Lead ID: {c.lead_id} | Status: {c.status} | CreatedAt: {c.created_at} | EndedAt: {c.ended_at}")
        
    print("\nLeads da Campanha 7 com status 'dialing' ou 'waiting_agent':")
    leads = Lead.query.filter(Lead.campaign_id==7, Lead.status.in_(['dialing', 'waiting_agent'])).all()
    for l in leads:
        print(f"Lead ID: {l.id} | Name: {l.name} | Status: {l.status}")
