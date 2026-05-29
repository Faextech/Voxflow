#!/bin/bash
# Poll GitHub — se main mudou, executa vps_deploy.sh.
# Instale via: bash scripts/install_vps_autodeploy.sh
set -euo pipefail

DEPLOY_DIR="${VOXFLOW_DEPLOY_DIR:-/opt/voxflow}"
REPO="${VOXFLOW_REPO:-Faextech/Voxflow}"
BRANCH="${VOXFLOW_BRANCH:-main}"
SHA_FILE="${DEPLOY_DIR}/.deploy-sha"
LOCK="${DEPLOY_DIR}/.deploy.lock"
DEPLOY_SCRIPT="${DEPLOY_DIR}/scripts/vps_deploy.sh"

if [ -f "$LOCK" ]; then
  exit 0
fi

REMOTE_SHA="$(curl -sf --max-time 15 \
  "https://api.github.com/repos/${REPO}/commits/${BRANCH}" \
  | sed -n 's/.*"sha"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
  | head -1)"

if [ -z "$REMOTE_SHA" ]; then
  echo "[$(date -Iseconds)] poll: não foi possível obter SHA remoto" >&2
  exit 0
fi

LOCAL_SHA="$(cat "$SHA_FILE" 2>/dev/null || echo none)"

if [ "$REMOTE_SHA" = "$LOCAL_SHA" ]; then
  exit 0
fi

echo "[$(date -Iseconds)] poll: novo commit ${REMOTE_SHA:0:8} (local ${LOCAL_SHA:0:8})"

touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT

if [ -x "$DEPLOY_SCRIPT" ]; then
  bash "$DEPLOY_SCRIPT"
else
  echo "ERRO: ${DEPLOY_SCRIPT} não encontrado ou não executável" >&2
  exit 1
fi
