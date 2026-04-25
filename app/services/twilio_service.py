import logging
import os
import re
from decimal import Decimal

from twilio.rest import Client

logger = logging.getLogger(__name__)


class InsufficientCreditError(Exception):
    """Levantada quando a empresa não tem saldo suficiente para iniciar uma chamada."""
    def __init__(self, company_id: int, balance: float, required: float):
        self.company_id = company_id
        self.balance = balance
        self.required = required
        super().__init__(
            f"Empresa {company_id} sem crédito suficiente: "
            f"saldo=R${balance:.2f} mínimo=R${required:.2f}"
        )


def normalize_phone_br(phone: str) -> str:
    """
    Garante que o número está em formato E.164 limpo (sem espaços, traços ou parênteses).
    - Remove todos os caracteres não numéricos
    - Se não começa com +55, adiciona o DDI do Brasil
    Exemplos:
      '41988578547'        -> '+5541988578547'
      '5541988578547'      -> '+5541988578547'
      '+5541988578547'     -> '+5541988578547'
      '(41) 98857-8547'   -> '+5541988578547'
      '+55 41 9235-3906'  -> '+554192353906'
    """
    cleaned = phone.strip()

    if cleaned.endswith(".0"):
        cleaned = cleaned[:-2]

    if cleaned.startswith("+"):
        digits_after_plus = re.sub(r"\D", "", cleaned[1:])
        if not digits_after_plus:
            return phone
        if digits_after_plus.startswith("55") and len(digits_after_plus) >= 12:
            return f"+{digits_after_plus}"
        return f"+{digits_after_plus}"

    digits = re.sub(r"\D", "", cleaned)

    if digits.startswith("0"):
        digits = digits[1:]

    if digits.startswith("55") and len(digits) >= 12:
        return f"+{digits}"

    return f"+55{digits}"


# Saldo mínimo para iniciar qualquer chamada (cobre ~1 minuto ao custo padrão)
# Evita iniciar chamadas quando o saldo está quase zerado e não cobriria nem o atendimento
_MIN_BALANCE_BRL = Decimal("0.50")


class TwilioService:
    """
    Serviço de chamadas Twilio.

    Use os factory methods para instanciar:
      TwilioService.from_company(company)  — produção: credenciais do tenant
      TwilioService.from_env()             — fallback dev: credenciais do .env
    """

    def __init__(self, account_sid: str, auth_token: str, phone_number: str, company=None):
        if not account_sid or not auth_token or not phone_number:
            raise ValueError(
                "Credenciais Twilio incompletas. "
                "account_sid, auth_token e phone_number são obrigatórios."
            )
        self.account_sid   = account_sid
        self.auth_token    = auth_token
        self.twilio_number = phone_number
        self.client        = Client(account_sid, auth_token)
        # Referência à empresa dona deste serviço (para verificação de crédito)
        self._company      = company

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "TwilioService":
        """Lê credenciais do .env — usar apenas em desenvolvimento/fallback."""
        return cls(
            account_sid  = (os.getenv("TWILIO_ACCOUNT_SID")  or "").strip(),
            auth_token   = (os.getenv("TWILIO_AUTH_TOKEN")   or "").strip(),
            phone_number = (os.getenv("TWILIO_PHONE_NUMBER") or "").strip(),
            company      = None,
        )

    @classmethod
    def from_company(cls, company) -> "TwilioService":
        """
        Lê credenciais do tenant (Company model).
        Faz fallback para .env se o tenant ainda não configurou sua conta Twilio.
        Isso garante compatibilidade durante a migração.
        """
        creds = company.get_twilio_credentials()

        account_sid  = (creds.get("account_sid")  or "").strip()
        auth_token   = (creds.get("auth_token")   or "").strip()
        phone_number = (creds.get("phone_number") or "").strip()

        if not account_sid:
            account_sid  = (os.getenv("TWILIO_ACCOUNT_SID")  or "").strip()
        if not auth_token:
            auth_token   = (os.getenv("TWILIO_AUTH_TOKEN")   or "").strip()
        if not phone_number:
            phone_number = (os.getenv("TWILIO_PHONE_NUMBER") or "").strip()

        return cls(account_sid, auth_token, phone_number, company=company)

    # ------------------------------------------------------------------
    # Verificação de crédito
    # ------------------------------------------------------------------

    def check_credit(self) -> None:
        """
        Verifica se a empresa tem saldo suficiente para iniciar uma chamada.
        Levanta InsufficientCreditError se não houver crédito.
        Se não houver empresa associada (from_env), passa direto — dev mode.
        """
        if self._company is None:
            return  # modo dev sem empresa — sem verificação

        balance = Decimal(str(self._company.get_balance()))
        if balance < _MIN_BALANCE_BRL:
            logger.warning(
                "[CREDIT GUARD] Chamada bloqueada — empresa=%s saldo=R$%.4f mínimo=R$%.2f",
                self._company.id, float(balance), float(_MIN_BALANCE_BRL),
            )
            raise InsufficientCreditError(
                company_id=self._company.id,
                balance=float(balance),
                required=float(_MIN_BALANCE_BRL),
            )

    # ------------------------------------------------------------------
    # Operações de chamada
    # ------------------------------------------------------------------

    def make_call(self, to_number, status_callback_url=None):
        # ── Bloqueio por crédito insuficiente ───────────────────────────
        self.check_credit()
        # ────────────────────────────────────────────────────────────────

        kwargs = {
            "to":    normalize_phone_br(to_number),
            "from_": self.twilio_number,
            "url":   "http://demo.twilio.com/docs/voice.xml",
        }
        if status_callback_url:
            kwargs["status_callback"]        = status_callback_url
            kwargs["status_callback_event"]  = ["initiated", "ringing", "answered", "completed"]
            kwargs["status_callback_method"] = "POST"

        call = self.client.calls.create(**kwargs)
        return call.sid

    def end_call(self, call_sid):
        if not call_sid:
            raise ValueError("call_sid é obrigatório para encerrar chamada.")
        call = self.client.calls(call_sid).update(status="completed")
        return call.sid

    def get_call(self, call_sid):
        if not call_sid:
            raise ValueError("call_sid é obrigatório para buscar chamada.")
        return self.client.calls(call_sid).fetch()
