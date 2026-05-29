#!/bin/bash
# Deploy stack completo VoxFlow na VPS Hostinger
# Uso: bash scripts/deploy_hostinger.sh SEU_IP_VPS
set -euo pipefail

IP="${1:-}"
if [ -z "$IP" ]; then
  echo "Uso: bash scripts/deploy_hostinger.sh SEU_IP_VPS"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

echo "==> Building Next.js frontend..."
cd "$ROOT/frontend"
npm ci --silent 2>/dev/null || npm install --silent
npm run build
cd "$ROOT"

echo "==> Gerando .env para IP ${IP}..."
python3 "$ROOT/scripts/generate_hostinger_env.py" --ip "$IP"

echo "==> Instalando Docker na VPS (se necessário)..."
ssh -o StrictHostKeyChecking=accept-new "root@${IP}" bash -s <<'REMOTE'
set -euo pipefail
if ! command -v docker &>/dev/null; then
  apt-get update -qq
  apt-get install -y docker.io docker-compose-v2 git curl ufw rsync
  systemctl enable docker && systemctl start docker
fi
ufw allow 22/tcp 2>/dev/null || true
ufw allow 80/tcp 2>/dev/null || true
ufw allow 8080/tcp 2>/dev/null || true
echo "y" | ufw enable 2>/dev/null || true
mkdir -p /opt/voxflow
REMOTE

echo "==> Enviando código..."
rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude 'node_modules' \
  --exclude '__pycache__' --exclude '*.db' --exclude 'instance' \
  "$ROOT/" "root@${IP}:/opt/voxflow/"

echo "==> Enviando .env..."
scp "$ROOT/deploy/hostinger/.env" "root@${IP}:/opt/voxflow/deploy/hostinger/.env"

echo "==> Build e start (pode levar 3-5 min)..."
ssh "root@${IP}" bash -s <<'REMOTE'
set -euo pipefail
cd /opt/voxflow/deploy/hostinger
chmod +x entrypoint.sh setup.sh 2>/dev/null || true
docker compose up -d --build nginx web
docker compose ps
REMOTE

echo ""
echo "==> Configurando Twilio webhooks..."
sleep 15
cd "$ROOT" && source .venv/bin/activate 2>/dev/null || true
python3 scripts/setup_twilio_completo.py --url "http://${IP}" 2>&1 | tail -20

echo ""
echo "============================================"
echo "  VoxFlow no ar na Hostinger!"
echo "  App:       http://${IP}/"
echo "  Health:    http://${IP}/health"
echo "  Login:     http://${IP}/login"
echo "  Evolution: http://${IP}:8080/"
echo "============================================"
echo ""
echo "Cadastre superadmin em http://${IP}/register"
echo "Email: master@faextech.com.br"
