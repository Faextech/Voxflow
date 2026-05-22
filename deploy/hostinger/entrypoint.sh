#!/bin/bash
set -euo pipefail

echo "==> Aguardando PostgreSQL..."
until python -c "import os,psycopg2; psycopg2.connect(os.environ['DATABASE_URL'])" 2>/dev/null; do
  sleep 2
done

echo "==> Inicializando schema..."
python <<'PY'
from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    db.create_all()
    print("create_all OK")
PY

echo "==> Rodando migrations..."
flask db upgrade

echo "==> Iniciando app..."
exec "$@"
