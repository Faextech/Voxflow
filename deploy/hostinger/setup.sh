#!/bin/bash
# Setup manual na VPS (se já clonou/copiou os arquivos)
set -euo pipefail
cd "$(dirname "$0")"

echo "==> VoxFlow — Setup Hostinger (stack completo)"

if ! command -v docker &>/dev/null; then
  apt-get update -qq
  apt-get install -y docker.io docker-compose-plugin git curl ufw
  systemctl enable docker && systemctl start docker
fi

if [ ! -f .env ]; then
  echo "ERRO: copie .env para deploy/hostinger/.env"
  echo "  python scripts/generate_hostinger_env.py --ip SEU_IP"
  exit 1
fi

chmod +x entrypoint.sh
docker compose build web
docker compose up -d
docker compose ps

echo ""
echo "App: http://$(curl -sf ifconfig.me 2>/dev/null || echo SEU_IP)/"
