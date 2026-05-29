#!/bin/bash
# Instala auto-deploy na VPS (cron a cada 3 min). Rode NO SERVIDOR como root.
set -euo pipefail

DEPLOY_DIR="${VOXFLOW_DEPLOY_DIR:-/opt/voxflow}"
INTERVAL="${VOXFLOW_POLL_MINUTES:-3}"

chmod +x "${DEPLOY_DIR}/scripts/vps_deploy.sh"
chmod +x "${DEPLOY_DIR}/scripts/vps_poll_deploy.sh"

CRON_LINE="*/${INTERVAL} * * * * ${DEPLOY_DIR}/scripts/vps_poll_deploy.sh >> ${DEPLOY_DIR}/.deploy.log 2>&1"

(crontab -l 2>/dev/null | grep -v 'vps_poll_deploy.sh'; echo "$CRON_LINE") | crontab -

echo "Auto-deploy instalado (poll a cada ${INTERVAL} min)."
echo "Log: ${DEPLOY_DIR}/.deploy.log"
echo ""
echo "Fluxo: git push origin main → VPS detecta em até ${INTERVAL} min → rebuild web"
echo ""
echo "Deploy manual imediato:"
echo "  bash ${DEPLOY_DIR}/scripts/vps_deploy.sh"
