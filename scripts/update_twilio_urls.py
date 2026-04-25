"""
Atualiza as URLs do Twilio para apontar para o backend em produção.
Execute UMA VEZ após o deploy no Railway:

    python scripts/update_twilio_urls.py

Requer as variáveis no .env:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
  TWILIO_TWIML_APP_SID, TWILIO_PHONE_NUMBER,
  BASE_URL (a URL pública do Railway)
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from twilio.rest import Client

ACCOUNT_SID    = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN     = os.getenv("TWILIO_AUTH_TOKEN")
TWIML_APP_SID  = os.getenv("TWILIO_TWIML_APP_SID")
PHONE_NUMBER   = os.getenv("TWILIO_PHONE_NUMBER")
BASE_URL       = (os.getenv("BASE_URL") or "").rstrip("/")

if not all([ACCOUNT_SID, AUTH_TOKEN, TWIML_APP_SID, PHONE_NUMBER, BASE_URL]):
    print("ERRO: variáveis faltando. Verifique .env")
    sys.exit(1)

if "ngrok" in BASE_URL or "localhost" in BASE_URL:
    print(f"AVISO: BASE_URL parece ser de desenvolvimento: {BASE_URL}")
    print("Para ngrok local, tudo bem. Para produção, use a URL do Railway.")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# ── 1. Atualizar TwiML App (webphone) ─────────────────────────────────────
print(f"\n1. Atualizando TwiML App {TWIML_APP_SID}...")
app = client.applications(TWIML_APP_SID).update(
    voice_url    = f"{BASE_URL}/api/twilio/browser-outgoing",
    voice_method = "POST",
)
print(f"   Voice URL: {app.voice_url}")

# ── 2. Atualizar número de telefone ───────────────────────────────────────
print(f"\n2. Buscando número {PHONE_NUMBER}...")
numbers = client.incoming_phone_numbers.list(phone_number=PHONE_NUMBER)

if not numbers:
    print(f"   ERRO: número {PHONE_NUMBER} não encontrado na conta")
    sys.exit(1)

number_sid = numbers[0].sid
updated = client.incoming_phone_numbers(number_sid).update(
    voice_url             = f"{BASE_URL}/api/twilio/voice",
    voice_method          = "POST",
    status_callback       = f"{BASE_URL}/api/twilio/status",
    status_callback_method = "POST",
)
print(f"   Número:          {updated.phone_number}")
print(f"   Voice URL:       {updated.voice_url}")
print(f"   Status Callback: {updated.status_callback}")

print("\n✓ URLs atualizadas com sucesso!")
print(f"\nResume:")
print(f"  Webphone:        {BASE_URL}/api/twilio/browser-outgoing")
print(f"  Voz inbound:     {BASE_URL}/api/twilio/voice")
print(f"  Status callback: {BASE_URL}/api/twilio/status")
print(f"  Billing webhook: {BASE_URL}/api/billing/payment/webhook")
