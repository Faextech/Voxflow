# NexDial — Guia de Deploy para Produção

> **Migração completa (conta nova):** veja [`deploy/MIGRACAO_DO_ZERO.md`](deploy/MIGRACAO_DO_ZERO.md)

> **Status da Arquitetura:** ✅ Pronto para produção com conta de teste Twilio.
> Troca para conta real = apenas atualizar variáveis de ambiente.

---

## Índice

1. [GitHub — subir o projeto](#1-github)
2. [Banco de Dados — PostgreSQL online](#2-banco-de-dados)
3. [Backend — deploy no Railway](#3-backend-railway)
4. [Variáveis de Ambiente](#4-variáveis)
5. [Migrations do banco](#5-migrations)
6. [Twilio — configurar webhooks](#6-twilio-webhooks)
7. [Twilio — subcontas por cliente (multi-conta)](#7-twilio-subcontas)
8. [Trocar conta Twilio (teste → real)](#8-trocar-twilio)
9. [Domínio customizado](#9-domínio)
10. [Checklist de Deploy](#10-checklist)

---

## 1. GitHub (Faextech)

Repositório: `https://github.com/Faextech/Voxflow` (conta Faextech)

```bash
cd /Users/allan/nexdial

git remote set-url origin https://github.com/Faextech/Voxflow.git
git remote -v   # confirmar origin → github.com/Faextech/Voxflow
git push -u origin main
```

No Railway: login com GitHub **Faextech** → **New Project → Deploy from GitHub repo** → `Faextech/Voxflow`.

**Importante:** desconecte o repositório antigo `shin-78/nexdial` do Railway (Settings → Disconnect) e revogue o acesso em GitHub → Settings → Applications.

**O `.gitignore` já protege:**
- `.env` — nunca vai para o Git ✅
- `.venv/` — ambiente Python local
- `*.db`, `instance/` — banco SQLite local
- `*.log`, `scratch/`

---

## 2. Banco de Dados

### Opção A — Supabase (gratuito, recomendado para começar)

1. Acesse https://supabase.com → **New Project**
2. Nome: `nexdial`, Região: **South America (São Paulo)**
3. **Settings → Database → Connection string → URI**:

```
postgresql://postgres:[SENHA]@db.[PROJETO_ID].supabase.co:5432/postgres
```

### Opção B — Railway PostgreSQL

No painel Railway: **New Service → Database → Add PostgreSQL**
A `DATABASE_URL` é gerada automaticamente.

### Opção C — Neon.tech (gratuito, serverless PostgreSQL)

Acesse https://neon.tech → criar projeto → copiar connection string.

---

## 3. Backend — Deploy no Railway

### 3.1 Criar projeto

1. https://railway.app → Login com GitHub
2. **New Project → Deploy from GitHub repo**
3. Selecione o repositório `nexdial`
4. Railway detecta o `Procfile` automaticamente ✅

### 3.2 Adicionar Redis (recomendado)

1. **+ New → Database → Redis**
2. Referenciar no serviço web: `REDIS_URL=${{Redis.REDIS_URL}}`

> Sem Redis o health check reporta `redis: fallback_memory` e o discador usa 1 worker in-memory.

### 3.3 O que acontece automaticamente

```
Procfile detectado →
  gunicorn "run:create_app()" \
    --workers 1 \
    --worker-class sync \
    --threads 4 \
    --bind 0.0.0.0:$PORT \
    --timeout 120
```

> **Por que 1 worker + 4 threads?**
> O auto-dialer usa `AUTO_DIALER_SESSIONS` e `ACTIVE_CONFERENCES_BY_AGENT`
> — dicionários em memória. Múltiplos workers teriam estados separados e
> causariam inconsistências. Com 1 worker + threads, o estado é compartilhado
> corretamente entre requisições simultâneas.

---

## 4. Variáveis de Ambiente

No Railway: **seu projeto → Settings → Variables → Add Variable**

Configure **TODAS** estas variáveis (template completo em [`deploy/railway.env.template`](deploy/railway.env.template)):

Gere chaves com: `python scripts/generate_production_keys.py`

```env
# Flask
FLASK_ENV=production
SECRET_KEY=<gere com: python scripts/generate_production_keys.py>

# Banco de Dados
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (recomendado)
REDIS_URL=${{Redis.REDIS_URL}}

# Criptografia de credenciais Twilio por tenant
FERNET_KEY=<gere com: python scripts/generate_production_keys.py>

# Admin
SUPERADMIN_EMAIL=seu@email.com

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+55XXXXXXXXXX
TWILIO_API_KEY=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_TWIML_APP_SID=APxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_VALIDATE_WEBHOOKS=true

# URLs (substituir pela URL real do Railway após deploy)
BASE_URL=https://nexdial-production.up.railway.app
PUBLIC_BASE_URL=https://nexdial-production.up.railway.app
CORS_ORIGINS=https://nexdial-production.up.railway.app

# Pagamento (opcional)
MERCADOPAGO_ACCESS_TOKEN=APP_USR-xxxxxxxxxxxxxxxx
```

---

## 5. Migrations do Banco

### Opção A — Railway CLI (recomendado)

```bash
npm install -g @railway/cli
railway login
railway run flask db upgrade
```

### Opção B — Localmente apontando para produção

```bash
cd /Users/allan/nexdial
source .venv/bin/activate

export DATABASE_URL="postgresql://postgres:SENHA@db.PROJETO.supabase.co:5432/postgres"
export FLASK_ENV=production
export SECRET_KEY="sua_chave"
export FERNET_KEY="sua_chave_fernet"

flask db upgrade
```

---

## 6. Twilio — Configurar Webhooks

Após o deploy, a URL pública será algo como:
`https://nexdial-production.up.railway.app`

### 6.1 TwiML App (webphone)

No Console Twilio → **Voice → TwiML Apps → seu app**:

| Campo | Valor |
|-------|-------|
| **Voice Request URL** | `https://nexdial-production.up.railway.app/api/twilio/browser-outgoing` |
| **Method** | POST |

### 6.2 Número Twilio (chamadas inbound/status callbacks)

No Console Twilio → **Phone Numbers → seu número**:

| Campo | Valor |
|-------|-------|
| **Voice URL** | `https://nexdial-production.up.railway.app/api/twilio/voice` |
| **Status Callback** | `https://nexdial-production.up.railway.app/api/twilio/status` |
| **Method** | POST |

### 6.3 Atualizar webhooks automaticamente

Após definir `BASE_URL` no `.env` local com credenciais Twilio:

```bash
python scripts/update_twilio_urls.py
```

### 6.4 Testar conectividade

```bash
python scripts/validate_production.py --url https://SUA-URL.up.railway.app
curl https://nexdial-production.up.railway.app/health
# {"status": "ok", "message": "VoxFlow operacional", "env": "production", "redis": "connected", ...}
```

---

## 7. Twilio — Subcontas por Cliente (Multi-conta)

### Arquitetura atual (Modo Simples — conta única)

```
.env
  TWILIO_ACCOUNT_SID = ACxxxx  ← conta de teste (fallback global)
  TWILIO_AUTH_TOKEN  = xxxx

Empresa (tabela companies)
  twilio_account_sid = NULL    ← usa fallback do .env
  twilio_auth_token  = NULL
  twilio_number      = NULL
```

### Arquitetura futura (Multi-conta — subconta por cliente)

```
.env
  TWILIO_ACCOUNT_SID = ACxxxx_MASTER  ← conta master

Empresa A (tabela companies)
  twilio_account_sid = ACxxxx_A      ← subconta isolada
  twilio_auth_token  = [criptografado com FERNET_KEY]
  twilio_number      = +5541xxxxxxxxx

Empresa B
  twilio_account_sid = ACxxxx_B
  twilio_auth_token  = [criptografado]
  twilio_number      = +5511xxxxxxxxx
```

### Criar subconta programaticamente

```python
from app.services.twilio_subaccount_service import create_subaccount
from app.models.company import Company

company = Company.query.get(company_id)
result = create_subaccount(company)
# result = {"subaccount_sid": "ACxxx...", "api_key_sid": "SKxxx..."}
```

### Configurar credenciais via API (admin)

```bash
# PUT /api/settings/twilio
curl -X PUT https://nexdial.up.railway.app/api/settings/twilio \
  -H "Authorization: Bearer SEU_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "account_sid": "ACxxxx",
    "auth_token": "xxxx",
    "phone_number": "+5511xxxx",
    "api_key": "SKxxxx",
    "api_secret": "xxxx",
    "twiml_app_sid": "APxxxx"
  }'
```

---

## 8. Trocar Conta Twilio (Teste → Real)

**Não requer refatoração de código.** Apenas:

### 8.1 Se usando conta global (1 conta para todos os clientes)

1. No Railway/painel: atualize as variáveis:
   ```
   TWILIO_ACCOUNT_SID = ACxxxx_REAL
   TWILIO_AUTH_TOKEN  = xxxx_REAL
   TWILIO_PHONE_NUMBER = +55XXXXXXXXXX_REAL
   TWILIO_API_KEY     = SKxxxx_REAL
   TWILIO_API_SECRET  = xxxx_REAL
   TWILIO_TWIML_APP_SID = APxxxx_REAL
   ```
2. Railway reinicia o serviço automaticamente
3. Atualizar webhooks no Console Twilio (se mudar conta)

### 8.2 Se usando subcontas por cliente

Via admin UI ou API `PUT /api/settings/twilio` para cada empresa.
Cada empresa tem suas credenciais isoladas — não afeta outras empresas.

### 8.3 Diferenças conta de TESTE vs REAL

| | Conta de Teste | Conta Real |
|-|---------------|------------|
| Chamadas para | Apenas números verificados | Qualquer número |
| Mensagem inicial | "This call is from Twilio..." | Nenhuma |
| Custo | Gratuito (crédito de teste) | Cobrado por minuto |
| Volume | Limitado | Ilimitado |

---

## 9. Domínio Customizado

No Railway: **Settings → Domains → Custom Domain**

Digite: `api.nexdial.com`

Configure o CNAME no seu DNS:
```
CNAME api  →  nexdial-production.up.railway.app
```

SSL é automático via Railway.

Atualize as variáveis:
```
BASE_URL=https://api.nexdial.com
PUBLIC_BASE_URL=https://api.nexdial.com
```

---

## 10. Checklist de Deploy

### Pré-deploy
- [ ] Repositório GitHub criado e código enviado (`git push`)
- [ ] Banco PostgreSQL criado (Supabase/Neon/Railway)
- [ ] `DATABASE_URL` copiada

### Railway
- [ ] Projeto criado, GitHub conectado
- [ ] Todas as variáveis de ambiente configuradas (ver seção 4)
- [ ] Deploy automático iniciado ao conectar GitHub

### Banco
- [ ] `flask db upgrade` executado (migrations aplicadas)

### Twilio
- [ ] URL pública do Railway copiada
- [ ] `BASE_URL` e `PUBLIC_BASE_URL` atualizados com URL real
- [ ] TwiML App no Console Twilio atualizado
- [ ] Número Twilio com Voice URL e Status Callback atualizados

### Validação
- [ ] `GET /health` retorna `{"status": "ok"}`
- [ ] Login funcionando
- [ ] Token do webphone gerado (`GET /api/webphone/token/<id>`)
- [ ] Chamada de teste realizada
- [ ] Webhook de status recebido (`/api/twilio/status`)

### Opcional
- [ ] Domínio customizado configurado
- [ ] MercadoPago webhook configurado
- [ ] Monitoramento de logs no Railway ativo
- [ ] Redis configurado (`redis: connected` no `/health`)
- [ ] `python scripts/validate_production.py` passa todos os checks
- [ ] Hostinger VPS: Evolution API preparada ([`deploy/hostinger/README.md`](deploy/hostinger/README.md))
