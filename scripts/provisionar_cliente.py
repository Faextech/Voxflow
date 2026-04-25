"""
Script de onboarding de cliente novo no NexDial.

O que faz:
  1. Lista as empresas sem subconta Twilio
  2. Você escolhe qual empresa provisionar
  3. Cria a subconta Twilio automaticamente
  4. Define custo por minuto (markup)
  5. Opcionalmente adiciona crédito inicial

Uso:
    cd /Users/allan/nexdial
    source .venv/bin/activate
    python scripts/provisionar_cliente.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("FLASK_ENV", "development")

from app import create_app
app = create_app()

with app.app_context():
    from app.extensions import db
    from app.models.company import Company
    from app.services.twilio_subaccount_service import create_subaccount

    # ── Listar empresas ────────────────────────────────────────────────────
    companies = Company.query.all()

    print("\n" + "="*55)
    print("  NexDial — Provisionamento de Cliente")
    print("="*55)
    print(f"\nEmpresas cadastradas ({len(companies)}):\n")

    for c in companies:
        tem_sub = "✓ subconta" if c.twilio_subaccount_sid else "✗ sem subconta"
        print(f"  [{c.id}] {c.name:<20} | Saldo: R${float(c.credit_balance):>8.2f} | {tem_sub}")

    print()
    try:
        escolha = int(input("Digite o ID da empresa para provisionar: ").strip())
    except (ValueError, KeyboardInterrupt):
        print("Cancelado.")
        sys.exit(0)

    company = Company.query.get(escolha)
    if not company:
        print(f"Empresa ID {escolha} não encontrada.")
        sys.exit(1)

    print(f"\nEmpresa selecionada: {company.name}")

    # ── Subconta Twilio ────────────────────────────────────────────────────
    if company.twilio_subaccount_sid:
        print(f"  Já possui subconta: {company.twilio_subaccount_sid}")
        recria = input("  Deseja ignorar e continuar para configurações? (s/n): ").strip().lower()
        if recria != "s":
            sys.exit(0)
    else:
        criar = input("\nCriar subconta Twilio para esta empresa? (s/n): ").strip().lower()
        if criar == "s":
            print("  Criando subconta no Twilio...")
            try:
                result = create_subaccount(company)
                print(f"  ✓ Subconta criada: {result['subaccount_sid']}")
                if result.get("api_key_sid"):
                    print(f"  ✓ API Key criada:  {result['api_key_sid']}")
            except Exception as e:
                print(f"  ✗ Erro ao criar subconta: {e}")
                print("  Continuando sem subconta (usará conta master).")

    # ── Custo por minuto ───────────────────────────────────────────────────
    print(f"\nCusto por minuto atual: R${float(company.cost_per_minute):.4f}/min")
    novo_custo = input("Novo custo por minuto (Enter para manter, ex: 0.35): ").strip()
    if novo_custo:
        try:
            company.cost_per_minute = float(novo_custo)
            print(f"  ✓ Custo definido: R${float(company.cost_per_minute):.4f}/min")
        except ValueError:
            print("  Valor inválido, mantendo atual.")

    # ── Crédito inicial ────────────────────────────────────────────────────
    print(f"\nSaldo atual: R${float(company.credit_balance):.2f}")
    credito_str = input("Adicionar crédito inicial? (Enter para pular, ex: 100.00): ").strip()
    if credito_str:
        try:
            credito = float(credito_str)
            tx = company.add_credit(credito, description="Crédito inicial (onboarding)")
            print(f"  ✓ R${credito:.2f} adicionado. Novo saldo: R${company.get_balance():.2f}")
        except ValueError:
            print("  Valor inválido, pulando.")

    # ── Salvar ─────────────────────────────────────────────────────────────
    db.session.commit()

    # ── Resumo final ───────────────────────────────────────────────────────
    creds = company.get_twilio_credentials()
    print("\n" + "="*55)
    print(f"  Empresa:       {company.name}")
    print(f"  Subconta SID:  {company.twilio_subaccount_sid or 'usa master'}")
    print(f"  Account SID:   {creds['account_sid'] or 'usa master'}")
    print(f"  Número:        {creds['phone_number'] or 'não configurado'}")
    print(f"  Custo/min:     R${float(company.cost_per_minute):.4f}")
    print(f"  Saldo:         R${company.get_balance():.2f}")
    print("="*55)
    print("\n✓ Cliente provisionado com sucesso!\n")
