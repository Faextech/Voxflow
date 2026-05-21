# Migração completa — do zero (Faextech + Railway + Twilio + Hostinger)

Guia para abandonar **toda** infra antiga (`shin-78`, Railway velho, Twilio velho) e subir tudo novo.

---

## Ordem de execução

```
GitHub Faextech → Railway (app+Postgres+Redis) → URL pública → Twilio → Validar → Hostinger
```

---

## 1. GitHub — Faextech/Voxflow

```bash
cd /Users/allan/nexdial
git remote set-url origin https://github.com/Faextech/Voxflow.git
git push -u origin main
```

Se der erro 403: faça login com conta **Faextech** (token ou limpe credencial `shin-78` no Keychain).

---

## 2. Railway — projeto novo (conta Faextech)

1. [railway.app](https://railway.app) → login GitHub **Faextech**
2. **New Project → Deploy from GitHub → `Faextech/Voxflow`**
3. **+ New → PostgreSQL**
4. **+ New → Redis** (obrigatório para discador/AMD estável)
5. Serviço web → **Settings → Networking → Generate Domain**
6. Copie a URL: `https://xxxx.up.railway.app`

### Variáveis Railway

Gere chaves:
```bash
python scripts/generate_production_keys.py
```

Imprima todas as variáveis prontas:
```bash
python scripts/print_railway_env.py --url https://SUA-URL.up.railway.app
```

Cole no Railway → Variables. Confirme:
- `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `REDIS_URL=${{Redis.REDIS_URL}}`
- `SUPERADMIN_EMAIL=seu@email.com`

Aguarde redeploy. Migrations rodam via `release: flask db upgrade`.

---

## 3. Twilio — conta nova (TwiML App, webhooks, AMD)

### 3.1 Criar recursos no Console (se ainda não tiver)

| Recurso | Onde criar |
|---------|------------|
| Account SID + Auth Token | Console → Account Info |
| Número BR | Phone Numbers → Buy (precisa `TWILIO_BUNDLE_SID` + `TWILIO_ADDRESS_SID` para BR) |
| API Key + Secret | Account → API Keys → Create |
| TwiML App | Voice → TwiML Apps → Create (`VoxFlow Webphone`) |

### 3.2 Atualizar `.env` local

```env
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+55...
TWILIO_API_KEY=SK...
TWILIO_API_SECRET=...
TWILIO_TWIML_APP_SID=AP...
TWILIO_BUNDLE_SID=BU...    # opcional BR
TWILIO_ADDRESS_SID=AD...   # opcional BR

PUBLIC_BASE_URL=https://SUA-URL.up.railway.app
BASE_URL=https://SUA-URL.up.railway.app
```

### 3.3 Configurar TUDO automaticamente

```bash
python scripts/setup_twilio_completo.py --url https://SUA-URL.up.railway.app
```

Isso configura:
- **TwiML App** → `/api/twilio/browser-outgoing` + status callback
- **Todos os números** → `/api/twilio/voice` + `/api/twilio/status`
- Valida API Key, conta, saldo

**AMD** (detecção de secretária eletrônica) não vai no Console — é automático via API:
- `/api/twilio/amd-hold` — hold enquanto analisa
- `/api/twilio/amd-callback` — resultado human/machine
- `/api/twilio/conference-events` — eventos da conferência

Funciona assim que `PUBLIC_BASE_URL` estiver correto no Railway.

### 3.4 Limpar credenciais antigas no banco (troca de conta master)

Se migrou de conta Twilio antiga:
```bash
python scripts/limpar_credenciais_twilio.py --force
python scripts/provisionar_cliente.py   # por empresa
```

---

## 4. Superadmin e validação

```bash
# Após railway login
railway login && railway link
railway run flask create-superadmin seu@email.com

# Validar endpoints
python scripts/validate_production.py --url https://SUA-URL.up.railway.app
```

Checklist manual:
- [ ] Login em `/login`
- [ ] Admin `/admin` → Diagnóstico Twilio (tudo verde)
- [ ] Dashboard → webphone conecta
- [ ] Chamada outbound (número verificado se conta teste)
- [ ] Inbound: ligar para número Twilio
- [ ] CRM `/crm` carrega
- [ ] `/health` → `"redis": "connected"`

---

## 5. Hostinger VPS — Evolution API (WhatsApp futuro)

```bash
scp -r deploy/hostinger/ root@IP_VPS:/opt/nexdial-comms/
ssh root@IP_VPS
cd /opt/nexdial-comms
cp .env.example .env   # editar senhas
bash setup.sh
```

WhatsApp **ainda não integrado** no backend — stack preparatório.

Telefonia (voz) fica na **Twilio + Railway**, não na Hostinger.

---

## 6. Desativar infra antiga

- [ ] Desconectar `shin-78/nexdial` do Railway antigo
- [ ] Revogar tokens GitHub da conta antiga
- [ ] Cancelar/desativar projeto Railway `web-production-c66e0`
- [ ] Desativar números/conta Twilio antiga (após validar nova)

---

## Comandos rápidos (resumo)

```bash
# 1. Push código
git push -u origin main

# 2. Imprimir env Railway
python scripts/print_railway_env.py --url https://SUA-URL.up.railway.app

# 3. Configurar Twilio
python scripts/setup_twilio_completo.py --url https://SUA-URL.up.railway.app

# 4. Validar
python scripts/validate_production.py --url https://SUA-URL.up.railway.app
```
