"""
Instrução para troca de conta master Twilio.

IMPORTANTE: subcontas são presas à conta master que as criou.
Não é possível migrar subcontas entre contas master diferentes.

O que precisa ser feito para trocar de conta master:

1. Comprar novos números na nova conta master
2. Recriar as subcontas na nova conta master
3. Atualizar o .env
4. Atualizar as URLs no Twilio (rodar scripts/update_twilio_urls.py)
5. Limpar as credenciais antigas das empresas no banco

Este script guia o processo de atualização do banco de dados
após você já ter criado a nova conta master no console Twilio.

Uso:
    cd /Users/allan/nexdial
    source .venv/bin/activate
    python scripts/trocar_conta_master.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("FLASK_ENV", "development")

print("""
╔══════════════════════════════════════════════════════════════╗
║          TROCA DE CONTA MASTER TWILIO — NexDial              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ATENÇÃO: Subcontas ficam presas à conta master que as criou ║
║  Trocar o master significa recriar TUDO do zero.             ║
║                                                              ║
║  Checklist ANTES de rodar este script:                       ║
║                                                              ║
║  [ ] 1. Criar nova conta no twilio.com (ou usar outra)       ║
║  [ ] 2. Comprar número brasileiro na nova conta              ║
║  [ ] 3. Criar TwiML App na nova conta                        ║
║  [ ] 4. Criar API Key na nova conta                          ║
║  [ ] 5. Atualizar o .env com as novas credenciais:           ║
║           TWILIO_ACCOUNT_SID=ACnova...                       ║
║           TWILIO_AUTH_TOKEN=nova_token...                     ║
║           TWILIO_PHONE_NUMBER=+55...novo                     ║
║           TWILIO_TWIML_APP_SID=APnovo...                     ║
║           TWILIO_API_KEY=SKnovo...                           ║
║           TWILIO_API_SECRET=novo_secret...                   ║
║  [ ] 6. Rodar: python scripts/update_twilio_urls.py          ║
║  [ ] 7. Rodar ESTE script para limpar o banco                ║
║  [ ] 8. Rodar: python scripts/provisionar_cliente.py         ║
║         para cada empresa (recriar subcontas na nova master) ║
╚══════════════════════════════════════════════════════════════╝
""")

continuar = input("Você já fez TODOS os passos acima? Digite SIM para continuar: ").strip()
if continuar != "SIM":
    print("Cancelado. Complete o checklist primeiro.")
    sys.exit(0)

from app import create_app
app = create_app()

with app.app_context():
    from app.extensions import db
    from app.models.company import Company

    companies = Company.query.all()
    print(f"\nEncontramos {len(companies)} empresa(s) no banco.")
    print("Vamos limpar as credenciais antigas e as subcontas para recriar na nova conta master.\n")

    for c in companies:
        print(f"  [{c.id}] {c.name}")
        print(f"    Subconta antiga: {c.twilio_subaccount_sid or 'nenhuma'}")

    confirmar = input("\nLimpar credenciais Twilio de todas as empresas? (s/n): ").strip().lower()
    if confirmar != "s":
        print("Cancelado.")
        sys.exit(0)

    for c in companies:
        c.twilio_subaccount_sid = None
        c.twilio_account_sid   = None
        c.twilio_auth_token    = None
        c.twilio_number        = None
        c.twilio_api_key       = None
        c.twilio_api_secret    = None
        c.twilio_twiml_app_sid = None

    db.session.commit()
    print("\n✓ Credenciais limpas.")
    print("\nAgora rode para cada empresa:")
    print("  python scripts/provisionar_cliente.py")
    print("\nIsso vai criar novas subcontas na nova conta master.\n")
