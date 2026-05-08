from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
import pyotp
import qrcode
import io
import base64


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False
    )

    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(50), nullable=False, default='admin')
    status = db.Column(db.String(50), nullable=False, default='active')
    is_online = db.Column(db.Boolean, nullable=False, default=False)

    # ── 2FA TOTP ──────────────────────────────────────────────────────────────
    totp_secret  = db.Column(db.String(64), nullable=True)   # base32 secret
    totp_enabled = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    company = db.relationship('Company', back_populates='users', lazy=True)
    agent_profile = db.relationship('Agent', back_populates='user', uselist=False, lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # ── 2FA helpers ───────────────────────────────────────────────────────────

    def generate_totp_secret(self) -> str:
        """Gera e armazena um novo secret TOTP. Ainda não ativa o 2FA."""
        self.totp_secret  = pyotp.random_base32()
        self.totp_enabled = False
        return self.totp_secret

    def get_totp_uri(self, issuer: str = "VoxFlow") -> str:
        """Retorna a URI otpauth:// para gerar QR code."""
        if not self.totp_secret:
            raise ValueError("TOTP secret não configurado")
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email,
            issuer_name=issuer,
        )

    def get_totp_qrcode_base64(self, issuer: str = "VoxFlow") -> str:
        """Gera QR code como PNG base64 para exibir no frontend."""
        uri  = self.get_totp_uri(issuer)
        img  = qrcode.make(uri)
        buf  = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def verify_totp(self, code: str) -> bool:
        """Valida código TOTP de 6 dígitos. Aceita 1 janela de ±30s."""
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(code, valid_window=1)