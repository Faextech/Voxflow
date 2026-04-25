"""
gunicorn.conf.py — Configuração do Gunicorn para produção (NexDial)

Uso:
  gunicorn "run:create_app()" -c gunicorn.conf.py

Notas:
  - workers=1 com threads é intencional: o auto-dialer usa estado em memória
    (AUTO_DIALER_SESSIONS, ACTIVE_CONFERENCES_BY_AGENT). Múltiplos workers
    teriam estados separados, causando inconsistências. Com threads (sync worker)
    o estado compartilhado é preservado corretamente.
  - Em escala futura: migrar AUTO_DIALER_SESSIONS para Redis.
"""
import multiprocessing
import os

# ── Workers ──────────────────────────────────────────────────────────────────
# 1 worker com threads — mantém estado em memória consistente (ver nota acima)
workers = 1
worker_class = "sync"
threads = 4

# ── Binding ───────────────────────────────────────────────────────────────────
port = os.getenv("PORT", "5000")
bind = f"0.0.0.0:{port}"

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout = 120        # Webhooks Twilio podem demorar
keepalive = 5        # Keep-alive para reduzir handshakes
graceful_timeout = 30

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog = "-"      # stdout
errorlog = "-"       # stderr
loglevel = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sμs'

# ── Performance ───────────────────────────────────────────────────────────────
preload_app = True   # Carrega app antes de forkar (economiza memória, detecta erros cedo)
max_requests = 500   # Reinicia worker a cada N requests (evita memory leaks)
max_requests_jitter = 50

# ── Segurança ─────────────────────────────────────────────────────────────────
limit_request_line = 4094
limit_request_fields = 100
