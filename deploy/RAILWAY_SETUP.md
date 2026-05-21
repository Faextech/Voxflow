# Railway — Setup Faextech (passo a passo)

Execute no painel [railway.app](https://railway.app) com login GitHub **Faextech**.

## 1. Novo projeto

1. **New Project → Deploy from GitHub repo**
2. Selecionar `shin-78/nexdial` (branch `main`)
3. Railway detecta o [`Procfile`](../Procfile) automaticamente

## 2. Serviços de dados

No mesmo projeto:

| Serviço | Ação | Variável gerada |
|---------|------|-----------------|
| PostgreSQL | + New → Database → PostgreSQL | `${{Postgres.DATABASE_URL}}` |
| Redis | + New → Database → Redis | `${{Redis.REDIS_URL}}` |

## 3. Variáveis do serviço web

Copie de [`railway.env.template`](railway.env.template) e preencha.

Gere chaves localmente:

```bash
python scripts/generate_production_keys.py
```

Cole no Railway → serviço web → **Variables**.

## 4. Domínio público

1. Serviço web → **Settings → Networking → Generate Domain**
2. Copie a URL (`https://xxxx.up.railway.app`)
3. Atualize no Railway:
   - `BASE_URL`
   - `PUBLIC_BASE_URL`
   - `CORS_ORIGINS`

## 5. Twilio webhooks

Com `.env` local apontando para a nova URL:

```bash
export BASE_URL=https://SUA-URL.up.railway.app
export PUBLIC_BASE_URL=$BASE_URL
# + credenciais TWILIO_* no .env
python scripts/update_twilio_urls.py
```

## 6. Migrations e superadmin

Migrations rodam automaticamente via `release: flask db upgrade` no Procfile.

Superadmin:

```bash
railway login
railway link
railway run flask create-superadmin seu@email.com
```

Ou registre em `/register` com o email definido em `SUPERADMIN_EMAIL` — promoção automática no startup.

## 7. Validar

```bash
python scripts/validate_production.py --url https://SUA-URL.up.railway.app
```

Esperado no `/health`: `"redis": "connected"`, `"status": "ok"`.

## Migração da instância antiga

Se já existe deploy em `web-production-c66e0.up.railway.app`:

1. Exporte dados com [`export_local_to_prod.py`](../export_local_to_prod.py) apontando `PUBLIC_BASE_URL` para a **nova** URL
2. Configure Twilio webhooks para a nova URL
3. Desative o projeto Railway antigo após validação
