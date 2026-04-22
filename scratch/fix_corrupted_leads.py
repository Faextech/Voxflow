"""
Script de emergência: limpa leads e chamadas presos em estado corrompido.
Executar ANTES de retomar a campanha após aplicar os fixes.

Uso: python scratch/fix_corrupted_leads.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.call import Call
from app.models.lead import Lead
from datetime import datetime

app = create_app()

with app.app_context():
    print("=" * 60)
    print("NexDial — Limpeza de Estado Corrompido")
    print("=" * 60)

    # 1. Chamadas presas em estados de pré-conexão há mais de 30s
    stuck_calls = Call.query.filter(
        Call.status.in_(["waiting_agent", "initiated", "ringing", "queued", "dialing"]),
    ).all()

    print(f"\n[CALLS] Encontradas {len(stuck_calls)} chamadas presas:")
    for c in stuck_calls:
        age = (datetime.utcnow() - c.created_at).total_seconds() if c.created_at else 0
        print(f"  Call id={c.id} lead={c.lead_id} campaign={c.campaign_id} status={c.status} age={age:.0f}s")
        c.status = "no_answer"
        c.ended_at = c.ended_at or datetime.utcnow()

    # 2. Leads presos em 'dialing'
    stuck_leads = Lead.query.filter(Lead.status == "dialing").all()
    print(f"\n[LEADS] Encontrados {len(stuck_leads)} leads presos em 'dialing':")
    for l in stuck_leads:
        print(f"  Lead id={l.id} name={l.name} campaign={l.campaign_id}")
        l.status = "new"

    db.session.commit()
    print("\n✅ Estado limpo! Pode retomar a campanha agora.")

    # 3. Resumo pós-limpeza
    print("\n[RESUMO PÓS-LIMPEZA por campanha]")
    from sqlalchemy import text
    result = db.session.execute(text("""
        SELECT campaign_id, status, count(*) as cnt
        FROM leads
        GROUP BY campaign_id, status
        ORDER BY campaign_id, status
    """))
    for row in result:
        print(f"  Campanha {row[0]}: status={row[1]} count={row[2]}")
