import sys
import os
import json

# Add current dir to path
sys.path.append(os.getcwd())

# We can't access AUTO_DIALER_SESSIONS directly because it's in-memory in the running process.
# But we can check the database for leads in 'dialing' status and calls in progress.

from app import create_app
from app.extensions import db
from app.models.lead import Lead
from app.models.call import Call
from app.models.campaign import Campaign

app = create_app()

with app.app_context():
    print("--- STUCK DIALING LEADS ---")
    stuck_leads = Lead.query.filter_by(status='dialing').all()
    for l in stuck_leads:
        print(f"Lead ID {l.id} | Name: {l.name} | Campaign: {l.campaign_id}")
        
    print("\n--- PENDING CALLS ---")
    pending_calls = Call.query.filter(Call.status.in_(['dialing', 'ringing', 'queued', 'waiting_agent'])).all()
    for c in pending_calls:
        print(f"Call ID {c.id} | Lead: {c.lead_id} | Status: {c.status} | SID: {c.call_sid} | Created: {c.created_at}")
        
    print("\n--- CAMPAIGN STATUSES ---")
    campaigns = Campaign.query.all()
    for c in campaigns:
        print(f"Campaign ID {c.id} | Name: {c.name} | Status: {c.status}")
