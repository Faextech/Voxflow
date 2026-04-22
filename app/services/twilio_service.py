import os
import re

from twilio.rest import Client


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
      '+55 41 9235-3906'  -> '+554192353906'   ← bug corrigido: + não pula sanitização
    """
    cleaned = phone.strip()

    # Proteção extra: remove sufixo ".0" que o Pandas adiciona ao ler Excel como número
    if cleaned.endswith(".0"):
        cleaned = cleaned[:-2]

    # Se começa com +, ainda sanitiza (remove espaços, traços, parênteses)
    # mas preserva o DDI internacional
    if cleaned.startswith("+"):
        digits_after_plus = re.sub(r"\D", "", cleaned[1:])
        if not digits_after_plus:
            return phone
        # Se o DDI for 55 (Brasil), aplica normalização completa a partir dos dígitos
        if digits_after_plus.startswith("55") and len(digits_after_plus) >= 12:
            return f"+{digits_after_plus}"
        # Outro país: retorna com + e dígitos limpos
        return f"+{digits_after_plus}"

    digits = re.sub(r"\D", "", cleaned)

    # Remove zero inicial (discagem local antiga)
    if digits.startswith("0"):
        digits = digits[1:]

    # Se começa com 55 e tem 12-13 dígitos, já tem DDI
    if digits.startswith("55") and len(digits) >= 12:
        return f"+{digits}"

    # Adiciona +55 (Brasil)
    return f"+55{digits}"


class TwilioService:
    """
    Serviço de chamadas Twilio.

    Use os factory methods para instanciar:
      TwilioService.from_company(company)  — produção: credenciais do tenant
      TwilioService.from_env()             — fallback dev: credenciais do .env
    """

    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        if not account_sid or not auth_token or not phone_number:
            raise ValueError(
                "Credenciais Twilio incompletas. "
                "account_sid, auth_token e phone_number são obrigatórios."
            )
        self.account_sid   = account_sid
        self.auth_token    = auth_token
        self.twilio_number = phone_number
        self.client        = Client(account_sid, auth_token)

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

        # Fallback para .env campo a campo
        if not account_sid:
            account_sid  = (os.getenv("TWILIO_ACCOUNT_SID")  or "").strip()
        if not auth_token:
            auth_token   = (os.getenv("TWILIO_AUTH_TOKEN")   or "").strip()
        if not phone_number:
            phone_number = (os.getenv("TWILIO_PHONE_NUMBER") or "").strip()

        return cls(account_sid, auth_token, phone_number)

    # ------------------------------------------------------------------
    # Operações de chamada
    # ------------------------------------------------------------------

    def make_call(self, to_number, status_callback_url=None):
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
