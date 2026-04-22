import os
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken

from app.extensions import db


class Company(db.Model):
    __tablename__ = "companies"

    id     = db.Column(db.Integer, primary_key=True)
    name   = db.Column(db.String(255), nullable=False)
    cnpj   = db.Column(db.String(50),  nullable=True)
    email  = db.Column(db.String(255), nullable=True)
    plan   = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50),  nullable=False, default="active")

    # ------------------------------------------------------------------
    # Credenciais Twilio
    #   twilio_auth_token  e twilio_api_secret são armazenados
    #   criptografados com Fernet (FERNET_KEY no .env).
    #   Os demais campos são IDs/números públicos — não criptografados.
    # ------------------------------------------------------------------
    twilio_account_sid   = db.Column(db.String(255), nullable=True)
    twilio_auth_token    = db.Column(db.String(512), nullable=True)   # encrypted
    twilio_number        = db.Column(db.String(50),  nullable=True)
    twilio_api_key       = db.Column(db.String(255), nullable=True)
    twilio_api_secret    = db.Column(db.String(512), nullable=True)   # encrypted
    twilio_twiml_app_sid = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    campaigns = db.relationship("Campaign", back_populates="company", lazy=True, cascade="all, delete-orphan")
    leads     = db.relationship("Lead",     back_populates="company", lazy=True, cascade="all, delete-orphan")
    calls     = db.relationship("Call",     back_populates="company", lazy=True, cascade="all, delete-orphan")
    users     = db.relationship("User",     back_populates="company", lazy=True, cascade="all, delete-orphan")
    agents    = db.relationship("Agent",    back_populates="company", lazy=True, cascade="all, delete-orphan")

    # ------------------------------------------------------------------
    # Fernet helpers (internos)
    # ------------------------------------------------------------------

    @staticmethod
    def _fernet() -> Fernet:
        key = (os.getenv("FERNET_KEY") or "").strip()
        if not key:
            raise RuntimeError(
                "FERNET_KEY não configurado no .env. "
                "Gere uma chave com: "
                "python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        return Fernet(key.encode())

    @staticmethod
    def _encrypt(value: str):
        """Criptografa uma string com Fernet. Retorna None se vazio."""
        if not value:
            return None
        return Company._fernet().encrypt(value.encode()).decode()

    @staticmethod
    def _decrypt(value: str):
        """Descriptografa um token Fernet. Retorna None se vazio ou inválido."""
        if not value:
            return None
        try:
            return Company._fernet().decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            return None

    # ------------------------------------------------------------------
    # API pública para credenciais
    # ------------------------------------------------------------------

    def set_twilio_credentials(
        self,
        account_sid=None,
        auth_token=None,
        phone_number=None,
        api_key=None,
        api_secret=None,
        twiml_app_sid=None,
    ):
        """
        Salva credenciais Twilio no tenant.
        Campos não fornecidos (None) são ignorados — valor existente é mantido.
        auth_token e api_secret são criptografados antes de persistir.
        """
        if account_sid is not None:
            self.twilio_account_sid = account_sid.strip() or None
        if auth_token is not None:
            self.twilio_auth_token = Company._encrypt(auth_token.strip()) if auth_token.strip() else None
        if phone_number is not None:
            self.twilio_number = phone_number.strip() or None
        if api_key is not None:
            self.twilio_api_key = api_key.strip() or None
        if api_secret is not None:
            self.twilio_api_secret = Company._encrypt(api_secret.strip()) if api_secret.strip() else None
        if twiml_app_sid is not None:
            self.twilio_twiml_app_sid = twiml_app_sid.strip() or None

    def get_twilio_credentials(self) -> dict:
        """
        Retorna as credenciais descriptografadas.
        Campos não configurados vêm como None.
        """
        return {
            "account_sid":   self.twilio_account_sid,
            "auth_token":    Company._decrypt(self.twilio_auth_token),
            "phone_number":  self.twilio_number,
            "api_key":       self.twilio_api_key,
            "api_secret":    Company._decrypt(self.twilio_api_secret),
            "twiml_app_sid": self.twilio_twiml_app_sid,
        }

    def has_twilio_configured(self) -> bool:
        """True se os três campos mínimos (sid, token, número) estão preenchidos."""
        creds = self.get_twilio_credentials()
        return bool(
            creds["account_sid"]
            and creds["auth_token"]
            and creds["phone_number"]
        )
