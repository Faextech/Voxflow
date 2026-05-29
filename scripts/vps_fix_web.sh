#!/bin/bash
# Corrige web crash loop na VPS — rode UMA vez como root:
#   curl -fsSL https://raw.githubusercontent.com/Faextech/Voxflow/main/scripts/vps_fix_web.sh | bash
set -euo pipefail

DEPLOY_DIR="${VOXFLOW_DEPLOY_DIR:-/opt/voxflow}"
COMPOSE_DIR="${DEPLOY_DIR}/deploy/hostinger"
REPO="${VOXFLOW_REPO:-https://github.com/Faextech/Voxflow.git}"
WORK="/tmp/voxflow-fix-$$"

echo "==> Baixando código corrigido do GitHub..."
git clone --depth 1 --branch main "$REPO" "$WORK"

echo "==> Sincronizando arquivos essenciais..."
rsync -a "$WORK/static/" "${DEPLOY_DIR}/static/"
rsync -a "$WORK/app/templates/" "${DEPLOY_DIR}/app/templates/"
rsync -a "$WORK/app/__init__.py" "${DEPLOY_DIR}/app/"
rsync -a "$WORK/deploy/hostinger/Dockerfile" "${DEPLOY_DIR}/deploy/hostinger/"
rsync -a "$WORK/deploy/hostinger/docker-compose.yml" "${DEPLOY_DIR}/deploy/hostinger/"
rsync -a "$WORK/scripts/vps_deploy.sh" "$WORK/scripts/vps_poll_deploy.sh" "$WORK/scripts/install_vps_autodeploy.sh" "${DEPLOY_DIR}/scripts/" 2>/dev/null || mkdir -p "${DEPLOY_DIR}/scripts"
chmod +x "${DEPLOY_DIR}/scripts/"*.sh 2>/dev/null || true

rm -rf "${DEPLOY_DIR}/app/config"
rm -rf "$WORK"

echo "==> Rebuild web (gunicorn)..."
cd "$COMPOSE_DIR"
docker compose build web --no-cache
docker compose up -d web

echo "==> Aguardando app subir..."
sleep 40

echo "==> Status:"
docker compose ps web
curl -s -o /dev/null -w "health: %{http_code}\n" http://localhost/health || true

echo "==> Instalando auto-deploy (cron)..."
bash "${DEPLOY_DIR}/scripts/install_vps_autodeploy.sh" 2>/dev/null || {
  ( crontab -l 2>/dev/null || true
    echo "*/3 * * * * ${DEPLOY_DIR}/scripts/vps_poll_deploy.sh >> ${DEPLOY_DIR}/.deploy.log 2>&1"
  ) | crontab -
  echo "Cron instalado manualmente."
}

echo ""
echo "Pronto. Teste: https://voxflow.tech/health"
