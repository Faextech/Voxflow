#!/bin/bash
# Corrige produção: frontend Next.js + nginx (HTTP + HTTPS se cert existir)
# Rodar NA VPS: curl -fsSL .../vps_fix_frontend.sh | bash
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

echo "==> Configurando nginx..."
mkdir -p "${COMPOSE_DIR}/nginx"
cp "$WORK/deploy/hostinger/nginx/nginx.conf" "${COMPOSE_DIR}/nginx/nginx.conf"
rsync -a "$WORK/deploy/hostinger/docker-compose.yml" "${COMPOSE_DIR}/docker-compose.yml"

# Detectar certificado SSL no host
SSL_DIR=""
for candidate in voxflow.tech www.voxflow.tech; do
  if [ -f "/etc/letsencrypt/live/${candidate}/fullchain.pem" ]; then
    SSL_DIR="/etc/letsencrypt/live/${candidate}"
    break
  fi
done

if [ -n "$SSL_DIR" ]; then
  echo "==> Certificado SSL encontrado: $SSL_DIR"
  cat >> "${COMPOSE_DIR}/nginx/nginx.conf" << EOF

server {
    listen 443 ssl;
    http2 on;
    server_name voxflow.tech www.voxflow.tech;

    client_max_body_size 20M;

    ssl_certificate     ${SSL_DIR}/fullchain.pem;
    ssl_certificate_key ${SSL_DIR}/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_protocols TLSv1.2 TLSv1.3;

    location /api/ {
        proxy_pass http://voxflow_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    location /auth/ {
        proxy_pass http://voxflow_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    location /socket.io/ {
        proxy_pass http://voxflow_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }

    location / {
        root /usr/share/nginx/html;
        try_files \$uri \$uri.html \$uri/ /index.html;
    }
}
EOF
else
  echo "==> AVISO: Sem certificado SSL em /etc/letsencrypt/live/ — só HTTP (porta 80)"
  echo "    Pastas disponíveis:"
  ls /etc/letsencrypt/live/ 2>/dev/null || echo "    (nenhuma)"
fi

if [ ! -f "${DEPLOY_DIR}/frontend/out/login.html" ]; then
  echo "ERRO: frontend/out/login.html não encontrado"
  exit 1
fi

echo "==> Reiniciando nginx..."
cd "$COMPOSE_DIR"
docker compose up -d --force-recreate nginx

echo "==> Verificando..."
sleep 3
docker compose ps nginx
docker compose logs nginx --tail 5 2>&1 || true
echo "--- HTTP ---"
curl -sI http://127.0.0.1/login | head -3
if [ -n "$SSL_DIR" ]; then
  echo "--- HTTPS ---"
  curl -skI https://127.0.0.1/login | head -3 || true
fi

echo ""
echo "✓ Site restaurado!"
echo "  HTTP:  http://voxflow.tech/login"
[ -n "$SSL_DIR" ] && echo "  HTTPS: https://voxflow.tech/login"
rm -rf "$WORK"
