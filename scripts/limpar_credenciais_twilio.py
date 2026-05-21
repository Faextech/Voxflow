#!/usr/bin/env python3
"""
Limpa credenciais Twilio de todas as empresas no banco.
Use após trocar a conta master Twilio.

Uso:
    python scripts/limpar_credenciais_twilio.py --force
    railway run python scripts/limpar_credenciais_twilio.py --force
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("FLASK_ENV", "production")

from app import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Executar sem confirmação")
    args = parser.parse_args()

    if not args.force:
        print("Use --force para confirmar limpeza de credenciais Twilio de todas as empresas.")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        from app.extensions import db
        from app.models.company import Company

        companies = Company.query.all()
        print(f"Limpando credenciais Twilio de {len(companies)} empresa(s)...")

        for c in companies:
            c.twilio_subaccount_sid = None
            c.twilio_account_sid = None
            c.twilio_auth_token = None
            c.twilio_number = None
            c.twilio_api_key = None
            c.twilio_api_secret = None
            c.twilio_twiml_app_sid = None
            print(f"  [{c.id}] {c.name}")

        db.session.commit()
        print("\n✓ Credenciais limpas. Rode provisionar_cliente.py por empresa.")


if __name__ == "__main__":
    main()
