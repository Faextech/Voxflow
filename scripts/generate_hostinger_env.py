#!/usr/bin/env python3
"""Gera deploy/hostinger/.env completo para stack VoxFlow na Hostinger."""

import argparse
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

TWILIO_KEYS = [
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
    "TWILIO_API_KEY", "TWILIO_API_SECRET", "TWILIO_TWIML_APP_SID",
    "TWILIO_BUNDLE_SID", "TWILIO_ADDRESS_SID",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", help="IP público da VPS")
    parser.add_argument("--domain", help="Domínio com HTTPS")
    args = parser.parse_args()

    if args.domain:
        base = f"https://{args.domain.strip().rstrip('/')}"
        evo = f"https://{args.domain.strip().rstrip('/')}:8080"
    elif args.ip:
        base = f"http://{args.ip.strip()}"
        evo = f"http://{args.ip.strip()}:8080"
    else:
        base = "http://SEU_IP"
        evo = "http://SEU_IP:8080"

    postgres_pw = secrets.token_urlsafe(24)
    evo_db_pw = secrets.token_urlsafe(24)
    evo_api_key = secrets.token_urlsafe(32)

    lines = [
        "# Gerado por scripts/generate_hostinger_env.py — NÃO commitar",
        f"POSTGRES_PASSWORD={postgres_pw}",
        f"DATABASE_URL=postgresql://voxflow:{postgres_pw}@postgres:5432/voxflow",
        "REDIS_URL=redis://redis:6379/0",
        "",
        "FLASK_ENV=production",
        "ENVIRONMENT=production",
        f"SECRET_KEY={secrets.token_urlsafe(48)}",
        f"FERNET_KEY={Fernet.generate_key().decode()}",
        f"BASE_URL={base}",
        f"PUBLIC_BASE_URL={base}",
        f"CORS_ORIGINS={base}",
        f"SUPERADMIN_EMAIL={os.getenv('SUPERADMIN_EMAIL', 'master@faextech.com.br')}",
        "TWILIO_VALIDATE_WEBHOOKS=true",
        "",
        f"EVOLUTION_DB_PASSWORD={evo_db_pw}",
        f"EVOLUTION_API_KEY={evo_api_key}",
        f"EVOLUTION_SERVER_URL={evo}",
        "",
    ]

    for k in TWILIO_KEYS:
        v = (os.getenv(k) or "").strip()
        if v:
            lines.append(f"{k}={v}")

    out = ROOT / "deploy" / "hostinger" / ".env"
    out.write_text("\n".join(lines) + "\n")
    print(f"✓ {out}")
    print(f"  App:       {base}/")
    print(f"  Evolution: {evo}/")


if __name__ == "__main__":
    main()
