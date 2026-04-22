from app import create_app
from app.extensions import db
from app.models.call import Call
from app.models.company import Company
from app.services.twilio_service import TwilioService
import os

app = create_app()

with app.app_context():
    call = Call.query.order_by(Call.id.desc()).first()
    if call:
        from app.services.call_bridge import ACTIVE_CONFERENCES_BY_AGENT
        # Mock item
        ACTIVE_CONFERENCES_BY_AGENT[call.agent_id] = {
            "conference_name": f"agent_bridge_{call.agent_id}",
            "campaign_id": call.campaign_id,
            "company_id": call.company_id
        }
        item = ACTIVE_CONFERENCES_BY_AGENT.get(call.agent_id)
        
        conf_name = item.get("conference_name")
        try:
            comp = Company.query.get(call.company_id)
            ts = TwilioService.from_company(comp)
            
            base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
            redirect_url = f"{base_url}/api/twilio/lead-to-bridge?c={conf_name}&lead_id={call.lead_id}"
            print("Would redirect to:", redirect_url)
            
            call_fetched = ts.client.calls(call.call_sid).fetch()
            print("Successfully fetched call. Status:", call_fetched.status)
            
            print("Attempting to UPDATE call URL (simulating redirect for AMD human)...")
            ts.client.calls(call.call_sid).update(url=redirect_url, method='POST')
            print("Update SUCCESSFUL!")
            
        except Exception as e:
            print("--- EXCEPTION CAUGHT ---")
            import traceback
            traceback.print_exc()
