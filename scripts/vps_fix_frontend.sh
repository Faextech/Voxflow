#!/bin/bash
# Corrige produção: copia frontend Next.js + nginx config e reinicia nginx.
# Rodar NA VPS: bash /opt/voxflow/scripts/vps_fix_frontend.sh
set -euo pipefail

DEPLOY_DIR="${VOXFLOW_DEPLOY_DIR:-/opt/voxflow}"
COMPOSE_DIR="${DEPLOY_DIR}/deploy/hostinger"
REPO="${VOXFLOW_REPO:-https://github.com/Faextech/Voxflow.git}"
BRANCH="${VOXFLOW_BRANCH:-main}"
WORK="${DEPLOY_DIR}/.fix-work"

echo "==> Baixando main do GitHub..."
rm -rf "$WORK"
git clone --depth 1 --branch "$BRANCH" "$REPO" "$WORK"

echo "==> Copiando frontend/out..."
mkdir -p "${DEPLOY_DIR}/frontend"
rsync -a --delete "$WORK/frontend/out/" "${DEPLOY_DIR}/frontend/out/"

echo "==> Copiando nginx.conf..."
mkdir -p "${COMPOSE_DIR}/nginx"
rsync -a "$WORK/deploy/hostinger/nginx/" "${COMPOSE_DIR}/nginx/"
rsync -a "$WORK/deploy/hostinger/docker-compose.yml" "${COMPOSE_DIR}/docker-compose.yml"

if [ ! -f "${DEPLOY_DIR}/frontend/out/login.html" ]; then
  echo "ERRO: frontend/out/login.html não encontrado após sync"
  exit 1
fi

echo "==> Reiniciando nginx..."
cd "$COMPOSE_DIR"
docker compose up -d --force-recreate nginx

echo "==> Verificando..."
sleep 2
docker compose exec -T nginx ls -la /usr/share/nginx/html/login.html
echo "--- teste local HTTP ---"
curl -sI http://127.0.0.1/login | head -5
echo "--- teste local HTTPS ---"
curl -skI https://127.0.0.1/login | head -5 || echo "(HTTPS: verifique certificados em /etc/letsencrypt/live/)"

echo ""
echo "✓ Pronto! Abra https://voxflow.tech/login (Ctrl+Shift+R para limpar cache)"
rm -rf "$WORK"
