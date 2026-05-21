#!/usr/bin/env python3
"""
Imprime variáveis formatadas para colar no Railway.

Uso:
    python scripts/print_railway_env.py
    python scripts/print_railway_env.py --url https://SEU-APP.up.railway.app
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="URL Railway (override .env)")
    args = parser.parse_args()

    base = (args.url or os.getenv("PUBLIC_BASE_URL") or os.getenv("BASE_URL") or "").strip().rstrip("/")
    if not base:
        print("ERRO: defina PUBLIC_BASE_URL ou use --url", file=sys.stderr)
        sys.exit(1)

    lines = [
        "FLASK_ENV=production",
        "ENVIRONMENT=production",
        f"SECRET_KEY={os.getenv('SECRET_KEY', '<gere: python scripts/generate_production_keys.py>')}",
        f"FERNET_KEY={os.getenv('FERNET_KEY', '<gere: python scripts/generate_production_keys.py>')}",
        "DATABASE_URL=${{Postgres.DATABASE_URL}}",
        "REDIS_URL=${{Redis.REDIS_URL}}",
        f"BASE_URL={base}",
        f"PUBLIC_BASE_URL={base}",
        f"CORS_ORIGINS={base}",
        f"SUPERADMIN_EMAIL={os.getenv('SUPERADMIN_EMAIL', 'seu@email.com')}",
        f"TWILIO_ACCOUNT_SID={os.getenv('TWILIO_ACCOUNT_SID', '')}",
        f"TWILIO_AUTH_TOKEN={os.getenv('TWILIO_AUTH_TOKEN', '')}",
        f"TWILIO_PHONE_NUMBER={os.getenv('TWILIO_PHONE_NUMBER', '')}",
        f"TWILIO_API_KEY={os.getenv('TWILIO_API_KEY', '')}",
        f"TWILIO_API_SECRET={os.getenv('TWILIO_API_SECRET', '')}",
        f"TWILIO_TWIML_APP_SID={os.getenv('TWILIO_TWIML_APP_SID', '')}",
        "TWILIO_VALIDATE_WEBHOOKS=true",
    ]
    if os.getenv("TWILIO_BUNDLE_SID"):
        lines.append(f"TWILIO_BUNDLE_SID={os.getenv('TWILIO_BUNDLE_SID')}")
    if os.getenv("TWILIO_ADDRESS_SID"):
        lines.append(f"TWILIO_ADDRESS_SID={os.getenv('TWILIO_ADDRESS_SID')}")
    if os.getenv("MERCADOPAGO_ACCESS_TOKEN"):
        lines.append(f"MERCADOPAGO_ACCESS_TOKEN={os.getenv('MERCADOPAGO_ACCESS_TOKEN')}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
