#!/bin/bash
set -euo pipefail
echo "==> Aguardando PostgreSQL..."
until python -c "import os,psycopg2; psycopg2.connect(os.environ['DATABASE_URL'])" 2>/dev/null; do
  sleep 2
done
echo "==> Rodando migrations..."
flask db upgrade
echo "==> Iniciando app..."
exec "$@"
