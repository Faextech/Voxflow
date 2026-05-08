"""
Script para exportar leads/campanhas do SQLite local e importar via API REST no Railway.

Uso:
    python export_local_to_prod.py --token SEU_JWT_TOKEN [--dry-run]

Flags:
    --dry-run   Apenas mostra o que seria importado, sem fazer chamadas reais
"""
import argparse
import csv
import io
import json
import sqlite3
import sys
import urllib.request
import urllib.error

RAILWAY_URL = "https://web-production-c66e0.up.railway.app"
LOCAL_DB    = "instance/nexdial.db"


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def api_json(method, path, token, body=None):
    url  = RAILWAY_URL + path
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": e.reason, "raw": raw[:200].decode("utf-8", errors="replace")}


def api_upload_csv(path, token, campaign_id, csv_bytes):
    """Faz POST multipart/form-data com o CSV."""
    url      = RAILWAY_URL + path
    boundary = b"----FormBoundaryVoxFlow"

    body  = b"--" + boundary + b"\r\n"
    body += b'Content-Disposition: form-data; name="campaign_id"\r\n\r\n'
    body += str(campaign_id).encode() + b"\r\n"
    body += b"--" + boundary + b"\r\n"
    body += b'Content-Disposition: form-data; name="file"; filename="leads.csv"\r\n'
    body += b"Content-Type: text/csv\r\n\r\n"
    body += csv_bytes + b"\r\n"
    body += b"--" + boundary + b"--\r\n"

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary.decode()}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": e.reason, "raw": raw[:200].decode("utf-8", errors="replace")}


# ─── SQLite helpers ───────────────────────────────────────────────────────────

def local_campaigns(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, dial_mode, retry_limit, mobile_only FROM campaigns ORDER BY id")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def local_leads(conn, campaign_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT name, email, company_name, job_title, city, state,
               numero_1, numero_2, numero_3, numero_4,
               numero_5, numero_6, numero_7, numero_8, notes
        FROM leads WHERE campaign_id = ?
    """, (campaign_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def leads_to_csv(leads):
    """Converte lista de leads para bytes CSV."""
    out  = io.StringIO()
    cols = ["name", "email", "company_name", "job_title", "city", "state",
            "numero_1", "numero_2", "numero_3", "numero_4",
            "numero_5", "numero_6", "numero_7", "numero_8", "notes"]
    w = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for l in leads:
        row = {k: (v or "") for k, v in l.items()}
        w.writerow(row)
    return out.getvalue().encode("utf-8")


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(token, dry_run):
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row

    print(f"\n{'='*60}")
    print(f"IMPORTAÇÃO: SQLite local → Railway{'  [DRY-RUN]' if dry_run else ''}")
    print(f"{'='*60}\n")

    # Campanhas remotas existentes
    status, remote_camps = api_json("GET", "/api/campaigns", token)
    if isinstance(remote_camps, dict):
        remote_camps = remote_camps.get("campaigns", [])
    if status != 200:
        print(f"[ERRO] Não conseguiu listar campanhas no Railway: {status} {remote_camps}")
        sys.exit(1)
    remote_by_name = {c["name"].strip().lower(): c for c in remote_camps}
    print(f"Railway: {len(remote_camps)} campanha(s) existente(s)")

    local_camps = local_campaigns(conn)
    print(f"Local:   {len(local_camps)} campanha(s) encontrada(s)\n")

    total_imported = 0

    for lc in local_camps:
        leads     = local_leads(conn, lc["id"])
        camp_name = lc["name"].strip()
        print(f"▶ '{camp_name}' — {len(leads)} leads locais")

        if not leads:
            print(f"  → Sem leads, pulando\n")
            continue

        # Busca ou cria campanha no Railway
        remote_camp = remote_by_name.get(camp_name.lower())
        if remote_camp:
            camp_id = remote_camp["id"]
            print(f"  → Campanha existente no Railway (id={camp_id})")
        else:
            if dry_run:
                print(f"  → [DRY-RUN] Criaria campanha '{camp_name}'")
                camp_id = 999
            else:
                payload = {
                    "name":        camp_name,
                    "description": lc.get("description") or "",
                    "dial_mode":   lc.get("dial_mode") or "manual",
                    "retry_limit": lc.get("retry_limit") or 3,
                    "mobile_only": bool(lc.get("mobile_only")),
                }
                status, resp = api_json("POST", "/api/campaign", token, payload)
                if status not in (200, 201):
                    print(f"  [ERRO] Criar campanha: {status} {resp}")
                    continue
                camp_id = resp.get("id") or resp.get("campaign", {}).get("id")
                remote_by_name[camp_name.lower()] = {"id": camp_id}
                print(f"  → Campanha criada no Railway (id={camp_id})")

        if dry_run:
            print(f"  → [DRY-RUN] Importaria {len(leads)} leads via CSV\n")
            continue

        # Importa via CSV
        csv_bytes = leads_to_csv(leads)
        status, resp = api_upload_csv("/api/leads/import", token, camp_id, csv_bytes)
        if status in (200, 201):
            imported = resp.get("imported", resp.get("created", len(leads)))
            total_imported += imported
            print(f"  ✓ {imported} leads importados")
            if resp.get("errors"):
                print(f"  ⚠  {len(resp['errors'])} erros: {resp['errors'][:3]}")
        else:
            print(f"  [ERRO] {status}: {str(resp)[:300]}")
        print()

    conn.close()
    print(f"{'='*60}")
    print(f"Concluído! Total importado: {total_imported} leads")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Importar dados locais para Railway")
    p.add_argument("--token",   required=True,       help="JWT token do superadmin")
    p.add_argument("--dry-run", action="store_true", help="Simula sem importar de verdade")
    args = p.parse_args()
    run(args.token, args.dry_run)
