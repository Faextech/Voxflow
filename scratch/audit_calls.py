import sys
sys.path.insert(0, '.')
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    calls = db.session.execute(text("""
        SELECT c.id, c.lead_id, l.name, c.status, c.phone_dialed,
               CASE WHEN c.call_sid IS NOT NULL THEN 'SIM' ELSE 'NAO' END as sid_ok,
               CASE WHEN c.ended_at IS NOT NULL THEN 'sim' ELSE 'nao' END as ended,
               c.created_at
        FROM calls c
        JOIN leads l ON c.lead_id = l.id
        WHERE c.campaign_id = 4
        ORDER BY c.id DESC
        LIMIT 15
    """)).fetchall()

    print("ID   Lead  Nome                            Status        Telefone         SID   Ended")
    print("-" * 100)
    for r in calls:
        nome = str(r[2] or "")[:30].ljust(30)
        status = str(r[3] or "").ljust(12)
        phone = str(r[4] or "").ljust(16)
        print(f"{r[0]:<5}{r[1]:<6}{nome}  {status}  {phone}  {r[5]}   {r[6]}")
