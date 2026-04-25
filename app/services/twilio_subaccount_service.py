"""
Gerencia subcontas Twilio por empresa (modelo master account + subaccounts).

Fluxo:
1. Admin cria empresa no NexDial
2. Sistema cria automaticamente uma subconta Twilio para esse cliente
3. Todas as chamadas da empresa usam a subconta isolada
4. Relatórios e custos ficam separados por subconta
"""

import logging
import os
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.extensions import db
from app.models.company import Company

logger = logging.getLogger(__name__)


def _master_client() -> Client:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN não configurados")
    return Client(sid, token)


def create_subaccount(company: Company) -> dict:
    """
    Cria uma subconta Twilio para a empresa e salva as credenciais no banco.
    Retorna dict com os dados da subconta criada.
    """
    if company.twilio_subaccount_sid:
        logger.warning(
            f"[TWILIO] Empresa {company.id} já possui subconta: {company.twilio_subaccount_sid}"
        )
        return {"subaccount_sid": company.twilio_subaccount_sid, "already_exists": True}

    client = _master_client()
    try:
        subaccount = client.api.v2010.accounts.create(
            friendly_name=f"NexDial - {company.name}"
        )
        logger.info(f"[TWILIO] Subconta criada: {subaccount.sid} para empresa {company.id}")
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao criar subconta: {e}")
        raise

    # Cria API Key dentro da subconta (para uso no webphone)
    sub_client = Client(subaccount.sid, subaccount.auth_token)
    try:
        api_key = sub_client.new_keys.create(friendly_name=f"NexDial-Key-{company.id}")
        api_key_sid = api_key.sid
        api_key_secret = api_key.secret
    except TwilioRestException as e:
        logger.warning(f"[TWILIO] Não foi possível criar API Key na subconta: {e}")
        api_key_sid = None
        api_key_secret = None

    # Persiste na empresa
    company.twilio_subaccount_sid = subaccount.sid
    company.set_twilio_credentials(
        account_sid=subaccount.sid,
        auth_token=subaccount.auth_token,
        api_key=api_key_sid,
        api_secret=api_key_secret,
    )
    db.session.commit()

    return {
        "subaccount_sid": subaccount.sid,
        "friendly_name": subaccount.friendly_name,
        "status": subaccount.status,
        "api_key_sid": api_key_sid,
    }


def suspend_subaccount(company: Company) -> bool:
    """Suspende a subconta Twilio da empresa (saldo zerado/bloqueio)."""
    if not company.twilio_subaccount_sid:
        return False
    client = _master_client()
    try:
        client.api.v2010.accounts(company.twilio_subaccount_sid).update(status="suspended")
        logger.info(f"[TWILIO] Subconta suspensa: {company.twilio_subaccount_sid}")
        return True
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao suspender subconta: {e}")
        return False


def activate_subaccount(company: Company) -> bool:
    """Reativa a subconta após recarga de crédito."""
    if not company.twilio_subaccount_sid:
        return False
    client = _master_client()
    try:
        client.api.v2010.accounts(company.twilio_subaccount_sid).update(status="active")
        logger.info(f"[TWILIO] Subconta reativada: {company.twilio_subaccount_sid}")
        return True
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao reativar subconta: {e}")
        return False


def get_subaccount_usage(company: Company, start_date: str, end_date: str) -> list:
    """Retorna uso de chamadas da subconta em um período (YYYY-MM-DD)."""
    if not company.twilio_subaccount_sid:
        return []
    client = _master_client()
    try:
        records = client.api.v2010.accounts(
            company.twilio_subaccount_sid
        ).usage.records.list(
            start_date=start_date,
            end_date=end_date,
            category="calls",
        )
        return [
            {
                "category": r.category,
                "description": r.description,
                "count": r.count,
                "usage": r.usage,
                "usage_unit": r.usage_unit,
                "price": r.price,
                "price_unit": r.price_unit,
            }
            for r in records
        ]
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao buscar uso: {e}")
        return []


def provision_phone_number(company: Company, area_code: str = "11", country: str = "BR") -> Optional[str]:
    """
    Compra e provisiona um número Twilio na subconta da empresa.
    Retorna o número provisionado ou None em caso de erro.
    """
    if not company.twilio_subaccount_sid:
        raise ValueError("Empresa não tem subconta Twilio configurada")

    creds = company.get_twilio_credentials()
    sub_client = Client(creds["account_sid"], creds["auth_token"])

    backend_url = os.getenv("BASE_URL", "http://localhost:5000")

    try:
        available = sub_client.available_phone_numbers(country).local.list(
            area_code=area_code, limit=1
        )
        if not available:
            logger.warning(f"[TWILIO] Nenhum número disponível no DDD {area_code}")
            return None

        purchased = sub_client.incoming_phone_numbers.create(
            phone_number=available[0].phone_number,
            voice_url=f"{backend_url}/api/twilio/voice",
            voice_method="POST",
            status_callback=f"{backend_url}/api/twilio/status-callback",
            status_callback_method="POST",
        )

        company.twilio_number = purchased.phone_number
        db.session.commit()
        logger.info(f"[TWILIO] Número {purchased.phone_number} provisionado para empresa {company.id}")
        return purchased.phone_number

    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao provisionar número: {e}")
        return None
