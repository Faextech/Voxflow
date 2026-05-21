#!/usr/bin/env python3
"""
Configuração COMPLETA da conta Twilio para NexDial/VoxFlow.

Configura TwiML App, todos os números, e valida credenciais (Voice SDK + AMD).

Uso:
    python scripts/setup_twilio_completo.py
    python scripts/setup_twilio_completo.py --url https://SEU-APP.up.railway.app
    python scripts/setup_twilio_completo.py --create   # cria TwiML App se não existir
    python scripts/setup_twilio_completo.py --dry-run

Requer no .env (ou --url):
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
    TWILIO_TWIML_APP_SID (ou --create)
    TWILIO_PHONE_NUMBER (opcional — atualiza todos os números da conta)
    BASE_URL / PUBLIC_BASE_URL
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Twilio import após load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

WEBHOOKS = {
    "twiml_app_voice": "/api/twilio/browser-outgoing",
    "inbound_voice": "/api/twilio/voice",
    "status": "/api/twilio/status",
    "amd_hold": "/api/twilio/amd-hold",
    "amd_callback": "/api/twilio/amd-callback",
    "conference_events": "/api/twilio/conference-events",
    "billing": "/api/billing/payment/webhook",
}


def _base_url(override: str | None) -> str:
    url = (override or os.getenv("PUBLIC_BASE_URL") or os.getenv("BASE_URL") or "").strip().rstrip("/")
    if not url:
        print("ERRO: defina BASE_URL/PUBLIC_BASE_URL no .env ou use --url")
        sys.exit(1)
    if "localhost" in url or "ngrok" in url:
        print(f"AVISO: URL parece ser de desenvolvimento: {url}")
    return url


def _client() -> Client:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        print("ERRO: TWILIO_ACCOUNT_SID e TWILIO_AUTH_TOKEN são obrigatórios")
        sys.exit(1)
    return Client(sid, token)


def verify_account(client: Client) -> dict:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    acc = client.api.accounts(sid).fetch()
    bal = client.balance.fetch()
    return {
        "status": acc.status,
        "friendly_name": acc.friendly_name,
        "balance": bal.balance,
        "currency": bal.currency,
    }


def verify_api_key(client: Client) -> dict:
    key_sid = os.getenv("TWILIO_API_KEY")
    secret = os.getenv("TWILIO_API_SECRET")
    if not key_sid or not secret:
        return {"ok": False, "error": "TWILIO_API_KEY / TWILIO_API_SECRET não configurados"}
    try:
        keys = client.keys.list(limit=20)
        found = any(k.sid == key_sid for k in keys)
        return {"ok": found, "sid": key_sid, "found_in_account": found}
    except TwilioRestException as e:
        return {"ok": False, "error": str(e)}


def create_twiml_app(client: Client, base: str) -> str:
    app = client.applications.create(
        friendly_name="VoxFlow Webphone",
        voice_url=f"{base}{WEBHOOKS['twiml_app_voice']}",
        voice_method="POST",
        status_callback=f"{base}{WEBHOOKS['status']}",
        status_callback_method="POST",
    )
    print(f"\n✓ TwiML App CRIADO: {app.sid}")
    print(f"  Adicione ao .env e Railway: TWILIO_TWIML_APP_SID={app.sid}")
    return app.sid


def update_twiml_app(client: Client, app_sid: str, base: str, dry_run: bool) -> dict:
    voice_url = f"{base}{WEBHOOKS['twiml_app_voice']}"
    status_cb = f"{base}{WEBHOOKS['status']}"
    if dry_run:
        return {"sid": app_sid, "voice_url": voice_url, "status_callback": status_cb, "dry_run": True}
    app = client.applications(app_sid).update(
        voice_url=voice_url,
        voice_method="POST",
        status_callback=status_cb,
        status_callback_method="POST",
    )
    return {
        "sid": app.sid,
        "friendly_name": app.friendly_name,
        "voice_url": app.voice_url,
        "status_callback": app.status_callback,
    }


def update_all_numbers(client: Client, base: str, preferred: str | None, dry_run: bool) -> list:
    voice_url = f"{base}{WEBHOOKS['inbound_voice']}"
    status_cb = f"{base}{WEBHOOKS['status']}"
    numbers = client.incoming_phone_numbers.list()
    if not numbers:
        print("AVISO: nenhum número encontrado na conta Twilio")
        return []

    updated = []
    for num in numbers:
        if dry_run:
            updated.append({"phone": num.phone_number, "voice_url": voice_url, "dry_run": True})
            continue
        u = client.incoming_phone_numbers(num.sid).update(
            voice_url=voice_url,
            voice_method="POST",
            status_callback=status_cb,
            status_callback_method="POST",
        )
        updated.append({
            "phone": u.phone_number,
            "voice_url": u.voice_url,
            "status_callback": u.status_callback,
            "primary": preferred and u.phone_number == preferred,
        })
    return updated


def print_amd_info(base: str):
    print("\n── AMD (Automated — configurado via API nas chamadas outbound) ──")
    print("  Não precisa configurar no Console Twilio. Endpoints usados:")
    for name in ("amd_hold", "amd_callback", "status", "conference_events"):
        print(f"    {base}{WEBHOOKS[name]}")
    print("  Parâmetros AMD (auto_dialer): machine_detection=Enable, async_amd=true")


def main():
    parser = argparse.ArgumentParser(description="Setup completo Twilio NexDial/VoxFlow")
    parser.add_argument("--url", help="URL pública Railway (override .env)")
    parser.add_argument("--create", action="store_true", help="Criar TwiML App se TWIML_TWIML_APP_SID ausente")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar o que seria feito")
    args = parser.parse_args()

    base = _base_url(args.url)
    client = _client()

    print(f"\n{'='*60}")
    print("  NexDial/VoxFlow — Setup Twilio Completo")
    print(f"  Base URL: {base}")
    print(f"{'='*60}")

    # 1. Conta
    print("\n1. Verificando conta Twilio...")
    acc = verify_account(client)
    print(f"   Conta: {acc['friendly_name']} ({acc['status']})")
    print(f"   Saldo: {acc['balance']} {acc['currency']}")

    # 2. API Key
    print("\n2. Verificando API Key (Voice SDK / webphone)...")
    key_info = verify_api_key(client)
    if key_info.get("ok"):
        print(f"   OK — {key_info['sid']}")
    else:
        print(f"   FALHA — {key_info.get('error', 'API Key não encontrada na conta')}")
        print("   Crie em: Twilio Console → Account → API Keys → Create API Key")
        print("   Salve TWILIO_API_KEY e TWILIO_API_SECRET no Railway (secret só aparece uma vez)")

    # 3. TwiML App
    app_sid = (os.getenv("TWILIO_TWIML_APP_SID") or "").strip()
    print("\n3. Configurando TwiML App (webphone outgoing)...")
    if not app_sid:
        if args.create and not args.dry_run:
            app_sid = create_twiml_app(client, base)
        else:
            print("   ERRO: TWILIO_TWIML_APP_SID não definido. Use --create ou crie no Console.")
            sys.exit(1)
    else:
        app = update_twiml_app(client, app_sid, base, args.dry_run)
        print(f"   SID:     {app['sid']}")
        print(f"   Voice:   {app['voice_url']}")
        print(f"   Status:  {app['status_callback']}")

    # 4. Números
    preferred = os.getenv("TWILIO_PHONE_NUMBER")
    print("\n4. Configurando números de telefone (inbound + status)...")
    nums = update_all_numbers(client, base, preferred, args.dry_run)
    for n in nums:
        mark = " ← TWILIO_PHONE_NUMBER" if n.get("primary") else ""
        print(f"   {n['phone']}{mark}")
        print(f"      Voice:  {n['voice_url']}")
        print(f"      Status: {n['status_callback']}")

    if preferred and not any(n.get("primary") for n in nums):
        print(f"\n   AVISO: TWILIO_PHONE_NUMBER={preferred} não encontrado na conta!")

    # 5. AMD info
    print_amd_info(base)

    # 6. Resumo Railway
    print("\n── Cole no Railway (Variables) ──")
    vars_to_set = [
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
        "TWILIO_API_KEY", "TWILIO_API_SECRET", "TWILIO_TWIML_APP_SID",
        "TWILIO_BUNDLE_SID", "TWILIO_ADDRESS_SID",
    ]
    for v in vars_to_set:
        val = os.getenv(v)
        if val:
            preview = val[:8] + "..." if len(val) > 12 else val
            print(f"  {v}={preview}")
    print(f"  BASE_URL={base}")
    print(f"  PUBLIC_BASE_URL={base}")
    print(f"  CORS_ORIGINS={base}")
    print(f"  TWILIO_VALIDATE_WEBHOOKS=true")

    print("\n✓ Setup Twilio concluído!")
    if args.dry_run:
        print("(dry-run — nenhuma alteração feita na Twilio)")


if __name__ == "__main__":
    main()
