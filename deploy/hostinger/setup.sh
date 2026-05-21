#!/bin/bash
# Setup Hostinger VPS — Evolution API (WhatsApp preparatório)
set -euo pipefail

cd "$(dirname "$0")"

echo "==> NexDial/VoxFlow — Setup Hostinger (Evolution API)"

if ! command -v docker &>/dev/null; then
  echo "Instalando Docker..."
  apt-get update -qq
  apt-get install -y docker.io docker-compose-plugin ufw
  systemctl enable docker
  systemctl start docker
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "CRIADO .env — EDITE as senhas antes de continuar!"
  echo "  nano .env"
  exit 1
fi

if grep -q "change_me" .env; then
  echo "ERRO: edite .env e troque as senhas padrão (change_me...)"
  exit 1
fi

# Firewall básico
if command -v ufw &>/dev/null; then
  ufw allow 22/tcp 2>/dev/null || true
  ufw allow 80/tcp 2>/dev/null || true
  ufw allow 443/tcp 2>/dev/null || true
fi

docker compose up -d
docker compose ps

echo ""
echo "Evolution API em http://127.0.0.1:8080 (somente localhost)"
echo "Configure Nginx + SSL para acesso externo seguro."
echo "Integração com Railway ainda não implementada no backend."
