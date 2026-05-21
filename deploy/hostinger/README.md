# Hostinger VPS — Comunicação (Evolution API)

Stack preparatório para WhatsApp via Evolution API. **O backend NexDial ainda não consome esta API** — use apenas para preparar a infraestrutura.

## Pré-requisitos

- VPS Hostinger com Ubuntu 22.04+
- Acesso root via SSH
- Docker e Docker Compose instalados

## Setup rápido

```bash
# Na VPS
apt update && apt upgrade -y
apt install -y docker.io docker-compose-plugin ufw
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

mkdir -p /opt/nexdial-comms
cd /opt/nexdial-comms
```

Copie `docker-compose.yml` e crie `.env`:

```bash
cat > .env <<'EOF'
EVOLUTION_DB_PASSWORD=sua_senha_forte_aqui
EVOLUTION_API_KEY=sua_chave_api_forte_aqui
EOF

docker compose up -d
docker compose ps
curl -s http://127.0.0.1:8080/ | head
```

## Segurança

- A porta `8080` está bindada em `127.0.0.1` — acesso externo só via Nginx reverse proxy + SSL ou VPN.
- Troque `EVOLUTION_DB_PASSWORD` e `EVOLUTION_API_KEY` antes do primeiro `up`.
- Não commite o `.env` da VPS no Git.

## Próximos passos (código NexDial)

Quando integrar WhatsApp no backend Railway:

1. Adicionar `EVOLUTION_API_URL` e `EVOLUTION_API_KEY` nas variáveis Railway
2. Criar rotas webhook inbound no Flask
3. Implementar envio real no `automation_engine.py` e follow-ups

## Telefonia SIP / FreeSWITCH

Não implementado. A telefonia atual usa **Twilio na Railway** (Voice SDK + webhooks).
