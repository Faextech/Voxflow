import sys, os
sys.path.insert(0, '.')
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.models.agent import Agent
from app.services.call_bridge import ACTIVE_CONFERENCES_BY_AGENT, ACTIVE_CONFERENCES_BY_NAME

app = create_app()
with app.app_context():
    # Importar sessoes depois do app context
    from app.api.routes.auto_dialer import AUTO_DIALER_SESSIONS

    print("=" * 60)
    print("CAMPANHAS RUNNING/ACTIVE")
    campaigns = Campaign.query.filter(Campaign.status.in_(['running', 'active'])).all()
    print(f"  Total: {len(campaigns)}")
    for c in campaigns:
        new_leads = Lead.query.filter(
            Lead.campaign_id == c.id,
            Lead.status.in_(['new', 'novo'])
        ).count()
        dialing_leads = Lead.query.filter(
            Lead.campaign_id == c.id,
            Lead.status == 'dialing'
        ).count()
        all_leads = Lead.query.filter_by(campaign_id=c.id).count()
        print(f"  id={c.id} name={c.name} status={c.status}")
        print(f"    leads total={all_leads}  new={new_leads}  dialing={dialing_leads}")

    print()
    print("SESSOES EM MEMORIA (AUTO_DIALER_SESSIONS)")
    if not AUTO_DIALER_SESSIONS:
        print("  [VAZIO - sessao perdida ao reiniciar servidor]")
    for k, v in AUTO_DIALER_SESSIONS.items():
        print(f"  campaign={k} status={v.get('status')} company={v.get('company_id')}")

    print()
    print("AGENTES DISPONIVEIS")
    agents = Agent.query.filter(Agent.status.in_(['available', 'online', 'ready'])).all()
    print(f"  Total: {len(agents)}")
    for a in agents:
        conf = ACTIVE_CONFERENCES_BY_AGENT.get(a.id)
        print(f"  agent_id={a.id} status={a.status} conf_status={conf.get('status') if conf else 'nenhuma'}")

    print()
    print("CONFERENCES ATIVAS EM MEMORIA")
    print(f"  Total: {len(ACTIVE_CONFERENCES_BY_NAME)}")
    for name, item in ACTIVE_CONFERENCES_BY_NAME.items():
        print(f"  {name}: status={item.get('status')}")

    print("=" * 60)
