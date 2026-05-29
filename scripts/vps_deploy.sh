#!/bin/bash
# Deploy VoxFlow na VPS Hostinger — roda NO SERVIDOR (terminal web, cron ou SSH).
# Baixa main do GitHub, sincroniza paths seguros e rebuild do container web + nginx.
set -euo pipefail

DEPLOY_DIR="${VOXFLOW_DEPLOY_DIR:-/opt/voxflow}"
REPO="${VOXFLOW_REPO:-https://github.com/Faextech/Voxflow.git}"
BRANCH="${VOXFLOW_BRANCH:-main}"
COMPOSE_DIR="${DEPLOY_DIR}/deploy/hostinger"
WORK="${DEPLOY_DIR}/.deploy-work"
LOG="${DEPLOY_DIR}/.deploy.log"
MODE="${1:-frontend}"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

log "==> Iniciando deploy (branch=${BRANCH}, mode=${MODE})"

rm -rf "$WORK"
git clone --depth 1 --branch "$BRANCH" "$REPO" "$WORK"

RSYNC_EXCLUDES=(
  --exclude 'deploy/hostinger/.env'
  --exclude 'deploy/hostinger/twilio.env'
  --exclude '.git'
)

sync_path() {
  local src="$1" dst="$2"
  if [ -d "$WORK/$src" ] || [ -f "$WORK/$src" ]; then
    rsync -a "${RSYNC_EXCLUDES[@]}" "$WORK/$src" "$dst"
    log "    synced $src"
  fi
}

log "==> Sincronizando arquivos..."
sync_path "static/" "${DEPLOY_DIR}/static/"
sync_path "app/templates/" "${DEPLOY_DIR}/app/templates/"
sync_path "app/__init__.py" "${DEPLOY_DIR}/app/"
sync_path "frontend/out/" "${DEPLOY_DIR}/frontend/out/"
sync_path "scripts/vps_deploy.sh" "${DEPLOY_DIR}/scripts/"
sync_path "scripts/vps_poll_deploy.sh" "${DEPLOY_DIR}/scripts/"
sync_path "deploy/hostinger/Dockerfile" "${DEPLOY_DIR}/deploy/hostinger/"
sync_path "deploy/hostinger/docker-compose.yml" "${DEPLOY_DIR}/deploy/hostinger/"
sync_path "deploy/hostinger/nginx/" "${DEPLOY_DIR}/deploy/hostinger/nginx/"

if [ "$MODE" = "full" ]; then
  sync_path "app/api/" "${DEPLOY_DIR}/app/api/"
  sync_path "app/routes/" "${DEPLOY_DIR}/app/routes/"
  sync_path "app/services/" "${DEPLOY_DIR}/app/services/"
  sync_path "app/models/" "${DEPLOY_DIR}/app/models/"
  sync_path "migrations/" "${DEPLOY_DIR}/migrations/"
  sync_path "requirements.txt" "${DEPLOY_DIR}/"
  sync_path "config.py" "${DEPLOY_DIR}/"
  sync_path "run.py" "${DEPLOY_DIR}/"
  sync_path "Procfile" "${DEPLOY_DIR}/"
fi

REMOTE_SHA="$(git -C "$WORK" rev-parse HEAD)"
echo "$REMOTE_SHA" > "${DEPLOY_DIR}/.deploy-sha"
log "==> Commit: ${REMOTE_SHA:0:8}"

rm -rf "$WORK"

if [ ! -d "$COMPOSE_DIR" ]; then
  log "ERRO: ${COMPOSE_DIR} não encontrado"
  exit 1
fi

cd "$COMPOSE_DIR"

if [ "$MODE" = "full" ]; then
  log "==> Rebuild stack completo..."
  docker compose up -d --build
else
  log "==> Rebuild containers web + nginx (frontend Next.js)..."
  docker compose build web
  docker compose up -d web nginx
fi

docker compose ps web nginx 2>/dev/null || docker compose ps
log "==> Deploy concluído — https://voxflow.tech"
