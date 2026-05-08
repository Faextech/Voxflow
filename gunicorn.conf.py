"""
gunicorn.conf.py — Configuração do Gunicorn para produção (NexDial/VoxFlow)

Uso:
  gunicorn "run:create_app()" -c gunicorn.conf.py

Workers:
  - Com REDIS_URL configurado: múltiplos workers (2 × CPU) — estado persistido no Redis.
  - Sem REDIS_URL: 1 worker com 4 threads — fallback seguro para estado in-memory.

Migração concluída:
  AUTO_DIALER_SESSIONS  → Redis (app/api/routes/auto_dialer.py)
  ACTIVE_CONFERENCES_*  → Redis (app/services/call_bridge.py)
  Rate limiting login   → Redis (app/auth.py)
"""
import multiprocessing
import os

# ── Workers — escala conforme disponibilidade do Redis ───────────────────────
_redis_url = os.getenv("REDIS_URL", "")
if _redis_url:
    # Redis disponível: múltiplos workers compartilham estado via Redis
    workers      = min(multiprocessing.cpu_count() * 2 + 1, 8)
    worker_class = "sync"
    threads      = 2
else:
    # Sem Redis: 1 worker com threads — estado in-memory consistente
    workers      = 1
    worker_class = "sync"
    threads      = 4

# ── Binding ───────────────────────────────────────────────────────────────────
port = os.getenv("PORT", "5000")
bind = f"0.0.0.0:{port}"

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout          = 120  # Webhooks Twilio podem demorar
keepalive        = 5
graceful_timeout = 30

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog        = "-"
errorlog         = "-"
loglevel         = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sμs'

# ── Performance ───────────────────────────────────────────────────────────────
preload_app          = False  # False com múltiplos workers para evitar conflito de forks
max_requests         = 1000
max_requests_jitter  = 100

# ── Segurança ─────────────────────────────────────────────────────────────────
limit_request_line   = 4094
limit_request_fields = 100
