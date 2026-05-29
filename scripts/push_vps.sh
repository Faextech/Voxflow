#!/bin/bash
# Sync código para VPS e rebuild do container web (requer SSH na porta 22).
# Se SSH falhar, use auto-deploy na VPS: scripts/install_vps_autodeploy.sh
set -euo pipefail

IP="${1:-187.77.201.88}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "root@${IP}" 'echo ok' 2>/dev/null; then
  echo "SSH indisponível para ${IP}."
  echo ""
  echo "Fluxo alternativo:"
  echo "  1. git push origin main"
  echo "  2. Na VPS: bash /opt/voxflow/scripts/vps_deploy.sh"
  echo "  ou instale poll: bash /opt/voxflow/scripts/install_vps_autodeploy.sh"
  exit 1
fi

echo "==> Enviando código para root@${IP}:/opt/voxflow/ ..."
rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude 'node_modules' \
  --exclude '__pycache__' --exclude '*.db' --exclude 'instance' \
  --exclude 'deploy/hostinger/.env' --exclude 'deploy/hostinger/twilio.env' \
  "$ROOT/" "root@${IP}:/opt/voxflow/"

echo "==> Rebuild web ..."
ssh "root@${IP}" 'cd /opt/voxflow/deploy/hostinger && docker compose build web && docker compose up -d web && docker compose ps web'

echo ""
echo "==> Deploy concluído — https://voxflow.tech"
