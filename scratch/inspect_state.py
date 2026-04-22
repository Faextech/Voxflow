import sys
import os
import json

# Add current dir to path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models import Lead, Call, Campaign
from app.api.routes.twilio_voice import ACTIVE_CONFERENCES_BY_AGENT, ACTIVE_CONFERENCES_BY_NAME

app = create_app()

with app.app_context():
    print("--- ACTIVE CONFERENCES BY AGENT ---")
    for aid, item in ACTIVE_CONFERENCES_BY_AGENT.items():
        print(f"Agent {aid}: Lead {item.get('lead_id')} | Status: {item.get('status')} | Conf: {item.get('conference_name')}")
    
    print("\n--- ACTIVE CONFERENCES BY NAME ---")
    for name, item in ACTIVE_CONFERENCES_BY_NAME.items():
        print(f"Conf {name}: Lead {item.get('lead_id')} | Status: {item.get('status')} | Agent: {item.get('agent_id')}")

    print("\n--- RECENT CALLS (LAST 5) ---")
    recent_calls = Call.query.order_by(Call.created_at.desc()).limit(5).all()
    for c in recent_calls:
        print(f"ID {c.id} | Lead {c.lead_id} | Status {c.status} | SID {c.call_sid}")
