# Hostinger VPS — stack completo (substitui Railway)

Um único VPS roda **tudo**:

| Serviço | Função |
|---------|--------|
| **nginx** | Porta 80 → app |
| **web** | Flask/Gunicorn — CRM, login, Twilio webhooks |
| **postgres** | Banco principal |
| **redis** | Discador, sessões, AMD |
| **evolution-api** | WhatsApp (porta 8080) |

Twilio continua na **nuvem Twilio** — webhooks apontam para o IP/domínio da VPS.

## Plano recomendado Hostinger

**KVM 2** — 2 vCPU, 8 GB RAM (~R$ 44/mês)

## Deploy automático (do seu Mac)

Quando a VPS estiver criada com Ubuntu 22.04:

```bash
bash scripts/deploy_hostinger.sh SEU_IP_VPS
```

Isso faz:
1. Gera `.env` com senhas + Twilio do seu `.env` local
2. Instala Docker na VPS
3. Envia código via rsync
4. `docker compose build && up`
5. Configura webhooks Twilio

## Deploy manual (terminal web Hostinger)

```bash
apt update && apt install -y docker.io docker-compose-plugin git
git clone https://github.com/Faextech/Voxflow.git /opt/voxflow
cd /opt/voxflow
python3 scripts/generate_hostinger_env.py --ip SEU_IP   # ou copie .env do Mac
cd deploy/hostinger && bash setup.sh
```

## Após deploy

- App: `http://SEU_IP/`
- Register: `http://SEU_IP/register` com `master@faextech.com.br`
- Evolution: `http://SEU_IP:8080/`

## HTTPS (recomendado para Twilio produção)

Twilio exige **HTTPS** para webhooks em produção. Com domínio apontando para o IP:

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d app.seudominio.com
```

Atualize `BASE_URL` / `PUBLIC_BASE_URL` e rode `python scripts/setup_twilio_completo.py --url https://app.seudominio.com`

## Desativar Railway

Após validar Hostinger, delete o projeto `voxflow` no Railway para parar cobrança.
