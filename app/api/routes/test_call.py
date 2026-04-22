from flask import Blueprint, jsonify
from twilio.rest import Client
import os

test_call_bp = Blueprint("test_call", __name__, url_prefix="/api/test")


@test_call_bp.route("/call/<int:agent_id>", methods=["GET"])
def make_call(agent_id):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    client = Client(account_sid, auth_token)

    call = client.calls.create(
        to=f"client:agent_{agent_id}",
        from_=from_number,
        url="https://undependent-wealthiest-troy.ngrok-free.dev/api/twilio/voice"
    )

    return jsonify({
        "message": "ligação iniciada",
        "call_sid": call.sid
    }), 200