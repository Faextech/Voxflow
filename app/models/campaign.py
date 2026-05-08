from datetime import datetime
from app.extensions import db


class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False
    )

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='draft')
    dial_mode = db.Column(db.String(50), nullable=False, default='manual')
    retry_limit = db.Column(db.Integer, nullable=False, default=3)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    default_pipeline_id = db.Column(
        db.Integer,
        db.ForeignKey('pipelines.id', ondelete='SET NULL'),
        nullable=True
    )
    default_stage_id = db.Column(
        db.Integer,
        db.ForeignKey('pipeline_stages.id', ondelete='SET NULL'),
        nullable=True
    )

    # Filtro: quando True, pula números com padrão de telefone fixo (somente celulares)
    mobile_only = db.Column(db.Boolean, default=False, nullable=False, server_default='0')

    # ── Configurações de discagem ────────────────────────────────────────────
    # Timeout de ring antes de marcar no_answer (20-90s, padrão 50s)
    ring_timeout_seconds = db.Column(db.Integer, default=50, nullable=False, server_default='50')

    # ── Configurações AMD ────────────────────────────────────────────────────
    # Threshold em ms para diferenciar "alô humano" de caixa postal (padrão 6000ms)
    amd_duration_threshold_ms = db.Column(db.Integer, default=6000, nullable=False, server_default='6000')
    # O que fazer quando AMD retorna "unknown": send_to_agent | hangup | retry_later
    unknown_amd_action = db.Column(db.String(20), default='send_to_agent', nullable=False, server_default='send_to_agent')

    # ── Janela de discagem (compliance LGPD/PROCON) ──────────────────────────
    # Hora de início permitida (0-23), padrão 8h
    allowed_hours_start = db.Column(db.Integer, default=8, nullable=False, server_default='8')
    # Hora de fim permitida (0-23), padrão 20h
    allowed_hours_end = db.Column(db.Integer, default=20, nullable=False, server_default='20')
    # Fuso horário da campanha, padrão Brasília
    allowed_timezone = db.Column(db.String(50), default='America/Sao_Paulo', nullable=False, server_default='America/Sao_Paulo')
    # Dias da semana permitidos (CSV: 0=Dom,1=Seg,...,6=Sáb), padrão seg-sex
    allowed_weekdays = db.Column(db.String(20), default='1,2,3,4,5', nullable=False, server_default='1,2,3,4,5')

    # ── Caller ID rotation ───────────────────────────────────────────────────
    # CSV de números Twilio (E.164) a rotacionar. Vazio = usa número padrão da empresa.
    caller_id_pool = db.Column(db.Text, nullable=True)
    # Índice do próximo número a usar no pool (round-robin)
    caller_id_index = db.Column(db.Integer, default=0, nullable=False, server_default='0')

    # ── Script de chamada ────────────────────────────────────────────────────
    # Texto livre exibido no popup do operador durante a chamada (dicas de abordagem).
    call_script = db.Column(db.Text, nullable=True)

    # ── Modo preditivo (AMD-03) ──────────────────────────────────────────────
    # Fator de sobrecarga para discagem preditiva (ex: 1.5 = 1.5 chamadas/agente).
    # Usado apenas quando dial_mode = 'predictive'. Range: 1.0–3.0.
    predictive_ratio = db.Column(db.Float, default=1.5, nullable=False, server_default='1.5')

    company = db.relationship('Company', back_populates='campaigns', lazy=True)
    leads = db.relationship('Lead', back_populates='campaign', lazy=True, cascade='all, delete-orphan')
    calls = db.relationship('Call', back_populates='campaign', lazy=True, cascade='all, delete-orphan')

    default_pipeline = db.relationship('Pipeline', foreign_keys=[default_pipeline_id])
    default_stage = db.relationship('PipelineStage', foreign_keys=[default_stage_id])

    def next_caller_id(self):
        """
        Retorna o próximo número do pool em round-robin e avança o índice.
        Retorna None se o pool estiver vazio (usa número padrão da empresa).
        """
        pool_raw = (self.caller_id_pool or "").strip()
        if not pool_raw:
            return None
        numbers = [n.strip() for n in pool_raw.split(",") if n.strip()]
        if not numbers:
            return None
        idx = (self.caller_id_index or 0) % len(numbers)
        chosen = numbers[idx]
        self.caller_id_index = (idx + 1) % len(numbers)
        return chosen

    def is_within_dialing_window(self) -> tuple:
        """
        Verifica se o horário atual está dentro da janela de discagem configurada.
        Esquema de dias: 0=Domingo, 1=Segunda … 6=Sábado (igual ao padrão JS/DB).
        Returns (bool, str) — (permitido, motivo se bloqueado).
        """
        import logging
        _log = logging.getLogger(__name__)
        try:
            import pytz
            from datetime import datetime

            tz_name = self.allowed_timezone or 'America/Sao_Paulo'
            try:
                tz = pytz.timezone(tz_name)
            except pytz.exceptions.UnknownTimeZoneError:
                _log.warning("[DIALING_WINDOW] Timezone inválida '%s' na campanha %s — bloqueando discagem por segurança", tz_name, self.id)
                return False, f"Timezone inválida configurada: {tz_name}"

            now_local = datetime.now(tz)
            current_hour = now_local.hour

            # Mapeamento consistente: Python weekday() 0=Mon…6=Sun → nosso schema 0=Dom,1=Seg…6=Sáb
            _py_to_schema = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}
            current_day = _py_to_schema[now_local.weekday()]

            allowed_days = {int(d) for d in (self.allowed_weekdays or '1,2,3,4,5').split(',') if d.strip().isdigit()}
            if current_day not in allowed_days:
                day_names = {0: 'Domingo', 1: 'Segunda', 2: 'Terça', 3: 'Quarta', 4: 'Quinta', 5: 'Sexta', 6: 'Sábado'}
                return False, f"Dia não permitido ({day_names.get(current_day, str(current_day))})"

            start = self.allowed_hours_start if self.allowed_hours_start is not None else 8
            end   = self.allowed_hours_end   if self.allowed_hours_end   is not None else 20
            if not (start <= current_hour < end):
                return False, f"Fora do horário permitido ({start}h–{end}h, agora {current_hour}h)"

            return True, ""
        except Exception as e:
            # Falha inesperada → bloqueia por segurança (não permite discar fora de hora)
            _log.error("[DIALING_WINDOW] Erro inesperado na campanha %s: %s", self.id, e)
            return False, f"Erro ao verificar janela de discagem: {e}"
