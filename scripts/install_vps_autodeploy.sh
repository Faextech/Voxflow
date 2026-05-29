#!/bin/bash
# Instala auto-deploy na VPS (cron a cada 3 min). Rode NO SERVIDOR como root.
set -euo pipefail

DEPLOY_DIR="${VOXFLOW_DEPLOY_DIR:-/opt/voxflow}"
INTERVAL="${VOXFLOW_POLL_MINUTES:-3}"

chmod +x "${DEPLOY_DIR}/scripts/vps_deploy.sh"
chmod +x "${DEPLOY_DIR}/scripts/vps_poll_deploy.sh"

if ! command -v crontab >/dev/null 2>&1; then
  echo "Instalando cron..."
  apt-get update -qq && apt-get install -y cron
fi

systemctl enable cron 2>/dev/null || true
systemctl start cron 2>/dev/null || true

CRON_LINE="*/${INTERVAL} * * * * ${DEPLOY_DIR}/scripts/vps_poll_deploy.sh >> ${DEPLOY_DIR}/.deploy.log 2>&1"

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -v 'vps_poll_deploy.sh' > "$TMP" || true
echo "$CRON_LINE" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Auto-deploy instalado (poll a cada ${INTERVAL} min)."
echo "Log: ${DEPLOY_DIR}/.deploy.log"
echo ""
crontab -l | grep vps_poll || { echo "ERRO: cron não foi registrado"; exit 1; }
echo ""
echo "Fluxo: git push origin main → VPS detecta em até ${INTERVAL} min → rebuild web"
echo ""
echo "Deploy manual imediato:"
echo "  bash ${DEPLOY_DIR}/scripts/vps_deploy.sh"
