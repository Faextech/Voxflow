#!/usr/bin/env python3
"""
Validação pós-deploy do NexDial/VoxFlow.

Uso:
    python scripts/validate_production.py
    python scripts/validate_production.py --url https://seu-app.up.railway.app

Lê PUBLIC_BASE_URL ou BASE_URL do .env; aceita --url para override.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    status = "OK" if ok else "FALHA"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")


def fetch(url, method="GET", timeout=15):
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body
    except urllib.error.URLError as e:
        return 0, str(e.reason)


def main():
    parser = argparse.ArgumentParser(description="Valida deploy NexDial em produção")
    parser.add_argument("--url", help="URL base (override env)")
    args = parser.parse_args()

    base = (args.url or os.getenv("PUBLIC_BASE_URL") or os.getenv("BASE_URL") or "").rstrip("/")
    if not base:
        print("ERRO: defina PUBLIC_BASE_URL no .env ou use --url")
        sys.exit(1)

    print(f"\nValidando: {base}\n")

    # 1. Health
    status, body = fetch(f"{base}/health")
    health_ok = status == 200
    redis_status = ""
    if health_ok:
        try:
            data = json.loads(body)
            health_ok = data.get("status") == "ok"
            redis_status = data.get("redis", "?")
        except json.JSONDecodeError:
            health_ok = False
    check("GET /health", health_ok, f"redis={redis_status}" if redis_status else f"HTTP {status}")

    # 2. Login page
    status, _ = fetch(f"{base}/login")
    check("GET /login", status == 200, f"HTTP {status}")

    # 3. Admin page (pode redirecionar — 200 ou 302)
    status, _ = fetch(f"{base}/admin")
    check("GET /admin", status in (200, 302, 401), f"HTTP {status}")

    # 4. CRM page
    status, _ = fetch(f"{base}/crm")
    check("GET /crm", status in (200, 302, 401), f"HTTP {status}")

    # 5. Twilio ping (sem auth)
    status, body = fetch(f"{base}/api/twilio/ping")
    check("GET /api/twilio/ping", status == 200, f"HTTP {status}")

    # 6. Webphone token (requer auth — esperamos 401)
    status, _ = fetch(f"{base}/api/webphone/token/1")
    check("GET /api/webphone/token (sem auth → 401)", status in (401, 403), f"HTTP {status}")

    # 7. Billing page
    status, _ = fetch(f"{base}/billing")
    check("GET /billing", status in (200, 302, 401), f"HTTP {status}")

    passed = sum(1 for _, ok, _ in CHECKS if ok)
    total = len(CHECKS)
    print(f"\nResultado: {passed}/{total} checks passaram\n")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
