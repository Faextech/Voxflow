# VoxFlow — stack Hostinger VPS (produção)

**Leia primeiro:** [`docs/INFRA_CONTEXT.md`](../../docs/INFRA_CONTEXT.md)

| Serviço | Função |
|---------|--------|
| nginx | HTTPS `voxflow.tech` → app |
| web | Uvicorn + Flask |
| postgres / redis | DB + filas |
| worker_* / scheduler | Background jobs |
| evolution-api | WhatsApp legado `:8080` |

## Env (dois arquivos)

| Arquivo | Conteúdo |
|---------|----------|
| `.env` | App (DB, secrets, URLs) |
| `twilio.env` | **Somente Twilio** — credenciais master (nunca commitar; ver `docs/INFRA_CONTEXT.md`) |

```bash
cp .env.example .env          # ou generate_hostinger_env.py --domain voxflow.tech
cp twilio.env.example twilio.env   # cole TWILIO_AUTH_TOKEN da conta nova
python ../../scripts/sync_hostinger_env.py
```

## Deploy

### Automático (recomendado — sem SSH do Mac)

1. **Mac:** `git push origin main`
2. **VPS (uma vez):** copie os scripts e instale o poll:

```bash
# No terminal web Hostinger, após rsync ou clone dos scripts:
bash /opt/voxflow/scripts/install_vps_autodeploy.sh
```

A VPS verifica o GitHub a cada 3 minutos e faz rebuild do container `web` quando `main` muda.

Deploy manual imediato na VPS:

```bash
bash /opt/voxflow/scripts/vps_deploy.sh
```

### SSH / GitHub Actions (quando porta 22 estiver acessível)

Secrets no repositório: `VPS_HOST`, `VPS_SSH_KEY`, opcional `VPS_USER`.

Workflow: `.github/workflows/deploy-production.yml`

### Deploy inicial completo

```bash
bash scripts/deploy_hostinger.sh 187.77.201.88
```

## Twilio (conta nova)

```bash
# 1. Auth Token em twilio.env
# 2. Criar API Key + TwiML App + webhooks
python scripts/migrate_twilio_nova_conta.py --create --vps 187.77.201.88

# 3. Número DDD 41
python scripts/buy_twilio_br_number.py --area-code 41 --set-primary
```

## Railway

**Descontinuado.** Não usar `*.up.railway.app`.
