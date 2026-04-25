"""
fix_stuck_leads.py
Limpa o estado inconsistente após reinício do servidor:
1. Leads presos em 'dialing' → volta para 'new'
2. Campanhas com status inconsistente
"""
import sys
sys.path.insert(0, '.')

from app import create_app
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.extensions import db

app = create_app()
with app.app_context():
    # 1) Libera leads presos em 'dialing' (chamada perdida/servidor reiniciado)
    stuck = Lead.query.filter(Lead.status == 'dialing').all()
    print(f"Leads presos em 'dialing': {len(stuck)}")
    for lead in stuck:
        lead.status = 'new'
        print(f"  lead id={lead.id} name={lead.name!r} campaign={lead.campaign_id} → new")

    # 2) Campanhas 'running' sem sessão em memória → paused
    #    (evita que o frontend tente retomar uma sessão inexistente)
    running = Campaign.query.filter_by(status='running').all()
    for c in running:
        c.status = 'paused'
        print(f"  campanha id={c.id} running→paused (sessao perdida no restart)")

    db.session.commit()
    print("\nLimpeza concluída. Agora reinicie o discador pela interface.")
