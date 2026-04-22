"""
Reset de emergência: restaura leads marcados como no_answer/failed
por causa do parâmetro inválido silence_timeout=500 (Twilio rejeitou TODAS as chamadas).

Reverte leads de campanha específica de volta para "new" para que
o discador os reprocesse corretamente.
"""
import sys, os
sys.path.insert(0, ".")

from app import create_app
from app.extensions import db
from app.models.lead import Lead
from app.models.campaign import Campaign
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    # Busca campanhas em status "finished" ou "paused" com leads marcados
    # como no_answer nas últimas 2 horas (janela do problema)
    cutoff = datetime.utcnow() - timedelta(hours=2)
    
    # Conta leads afetados
    affected = Lead.query.filter(
        Lead.status == "no_answer",
        Lead.updated_at >= cutoff if hasattr(Lead, "updated_at") else True
    ).count()
    print(f"Leads no_answer nas últimas 2h: {affected}")
    
    # Lista campanhas com leads no_answer recentes
    campaigns = db.session.query(Lead.campaign_id).filter(
        Lead.status == "no_answer"
    ).distinct().all()
    
    print("\nCampanhas com leads no_answer:")
    for (cid,) in campaigns:
        camp = Campaign.query.get(cid)
        count = Lead.query.filter_by(campaign_id=cid, status="no_answer").count()
        total = Lead.query.filter_by(campaign_id=cid).count()
        print(f"  ID={cid} | {camp.name if camp else '?'} | no_answer={count}/{total} | status={camp.status if camp else '?'}")
    
    print("\n⚠️  Para resetar, execute com o ID da campanha:")
    print("   python reset_campaign_leads.py <campaign_id>")
    
    if len(sys.argv) > 1:
        cid = int(sys.argv[1])
        camp = Campaign.query.get(cid)
        if not camp:
            print(f"Campanha {cid} não encontrada!")
            sys.exit(1)
        
        # Reset leads no_answer → new para esta campanha
        n = Lead.query.filter_by(campaign_id=cid, status="no_answer").update({"status": "new"})
        
        # Reseta status da campanha para running (pronta para iniciar)
        camp.status = "paused"
        db.session.commit()
        print(f"\n✅ {n} leads resetados para 'new' na campanha {cid} ({camp.name})")
        print(f"✅ Campanha status → 'paused' (pronta para iniciar)")
