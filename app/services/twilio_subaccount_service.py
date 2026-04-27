"""
Gerencia subcontas Twilio por empresa (modelo master account + subaccounts).

Fluxo:
1. Admin cria empresa no VoxFlow
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
        logger.info(f"[TWILIO] Empresa {company.id} já possui subconta: {company.twilio_subaccount_sid}")
        # Tenta buscar credenciais se estiverem vazias
        creds = company.get_twilio_credentials()
        if creds.get("auth_token"):
            return {"subaccount_sid": company.twilio_subaccount_sid, "auth_token": creds["auth_token"]}

    client = _master_client()
    try:
        subaccount = client.api.v2010.accounts.create(
            friendly_name=f"VoxFlow - {company.name}"
        )
        logger.info(f"[TWILIO] Subconta criada: {subaccount.sid} para empresa {company.id}")
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao criar subconta: {e}")
        raise

    # Cria API Key dentro da subconta (para uso no webphone/Voice SDK)
    sub_client = Client(subaccount.sid, subaccount.auth_token)
    api_key_sid = None
    api_key_secret = None
    try:
        api_key = sub_client.new_keys.create(friendly_name=f"VoxFlow-Key-{company.id}")
        api_key_sid = api_key.sid
        api_key_secret = api_key.secret
    except TwilioRestException as e:
        logger.warning(f"[TWILIO] Não foi possível criar API Key na subconta: {e}")

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
        "auth_token": subaccount.auth_token,
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


def create_twiml_app(company: Company) -> Optional[str]:
    """Cria um TwiML App na subconta da empresa para uso com Voice SDK."""
    if not company.twilio_subaccount_sid:
        return None

    creds = company.get_twilio_credentials()
    sub_client = Client(creds["account_sid"], creds["auth_token"])
    backend_url = os.getenv("PUBLIC_BASE_URL") or os.getenv("BASE_URL") or "http://localhost:5000"

    try:
        app = sub_client.applications.create(
            friendly_name=f"VoxFlow App - {company.name}",
            voice_url=f"{backend_url}/api/twilio/browser-outgoing",
            voice_method="POST",
            status_callback=f"{backend_url}/api/twilio/status-callback",
            status_callback_method="POST"
        )
        company.twilio_twiml_app_sid = app.sid
        db.session.commit()
        logger.info(f"[TWILIO] TwiML App {app.sid} criado para empresa {company.id}")
        return app.sid
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao criar TwiML App: {e}")
        return None


def search_available_numbers(area_code: str = "11", country: str = "BR", limit: int = 5) -> list:
    """Retorna uma lista de números disponíveis para compra na Twilio.
    Sempre usa a conta master para garantir acesso sem restrições de bundle regulatório.
    """
    client = _master_client()

    results = []
    try:
        # 1. Tenta Local com DDD
        try:
            available = client.available_phone_numbers(country).local.list(area_code=area_code, limit=limit)
            results.extend(available)
        except Exception as e:
            logger.warning(f"[TWILIO] Erro na busca Local DDD {area_code}: {e}")
        
        # 2. Se não achou muitos, tenta Mobile com DDD
        if len(results) < limit:
            try:
                mobile = client.available_phone_numbers(country).mobile.list(area_code=area_code, limit=limit - len(results))
                results.extend(mobile)
            except Exception as e:
                logger.warning(f"[TWILIO] Erro na busca Mobile DDD {area_code}: {e}")

        # 3. Se ainda não achou NADA, tenta sem DDD (geral no país)
        if not results:
            logger.info(f"[TWILIO] Sem números no DDD {area_code}, buscando em todo o país {country}")
            try:
                any_local = client.available_phone_numbers(country).local.list(limit=limit)
                results.extend(any_local)
            except Exception as e:
                logger.warning(f"[TWILIO] Erro na busca Local geral: {e}")

        return [{"phone_number": n.phone_number, "friendly_name": n.friendly_name} for n in results]
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro crítico ao buscar números: {e}")
        return []


def _ensure_address_in_subaccount(company: Company, sub_client: Client) -> Optional[str]:
    """
    Garante que a subconta tem um endereço cadastrado na Twilio.
    Usa os dados regulatórios da empresa. Retorna o address_sid ou None.
    """
    try:
        existing = sub_client.addresses.list(limit=1)
        if existing:
            return existing[0].sid

        # Constrói endereço a partir dos dados regulatórios da empresa
        street = (company.reg_address or "Rua Sem Endereço, 1").strip()[:200]
        customer_name = (company.reg_name or company.name or "Cliente VoxFlow").strip()[:100]

        address = sub_client.addresses.create(
            customer_name=customer_name,
            street=street,
            city="São Paulo",
            region="SP",
            postal_code="01310-100",
            iso_country="BR",
            friendly_name=f"VoxFlow - {company.name}",
        )
        logger.info(f"[TWILIO] Endereço criado na subconta {company.twilio_subaccount_sid}: {address.sid}")
        return address.sid
    except TwilioRestException as e:
        logger.warning(f"[TWILIO] Não foi possível criar endereço na subconta: {e}")
        return None


def provision_phone_number(company: Company, area_code: str = "11", country: str = "BR", specific_number: str = None) -> Optional[str]:
    """
    Compra e provisiona um número Twilio usando a conta master com bundle e endereço aprovados.
    Números BR exigem bundle regulatório aprovado — compramos na master que já possui o bundle.
    O número fica salvo no banco vinculado à empresa; o roteamento por webhook identifica a empresa.
    """
    master = _master_client()
    backend_url = os.getenv("PUBLIC_BASE_URL") or os.getenv("BASE_URL") or "http://localhost:5000"
    bundle_sid  = os.getenv("TWILIO_BUNDLE_SID")
    address_sid = os.getenv("TWILIO_ADDRESS_SID")

    try:
        target_number = specific_number

        if not target_number:
            available = master.available_phone_numbers(country).local.list(area_code=area_code, limit=1)
            if not available:
                available = master.available_phone_numbers(country).local.list(limit=1)
            if not available:
                return {"error": "Nenhum número disponível no Brasil no momento"}
            target_number = available[0].phone_number

        purchase_params = dict(
            phone_number=target_number,
            voice_url=f"{backend_url}/api/twilio/voice",
            voice_method="POST",
            status_callback=f"{backend_url}/api/twilio/status",
            status_callback_method="POST",
        )
        if bundle_sid:
            purchase_params["bundle_sid"] = bundle_sid
        if address_sid:
            purchase_params["address_sid"] = address_sid

        purchased = master.incoming_phone_numbers.create(**purchase_params)

        company.twilio_number = purchased.phone_number
        db.session.commit()
        logger.info(f"[TWILIO] Número {purchased.phone_number} comprado (master) para empresa {company.id}")
        return purchased.phone_number

    except TwilioRestException as e:
        code = getattr(e, 'code', None)
        msg = f"Erro Twilio {code}: {e.msg}" if code else str(e)
        logger.error(f"[TWILIO] Erro ao provisionar número {specific_number or 'auto'}: {msg}")
        return {"error": msg}


def list_subaccount_numbers(company: Company) -> list:
    """Lista todos os números de telefone adquiridos na subconta da empresa."""
    if not company.twilio_subaccount_sid:
        return []
    creds = company.get_twilio_credentials()
    sub_client = Client(creds["account_sid"], creds["auth_token"])
    try:
        numbers = sub_client.incoming_phone_numbers.list()
        return [
            {"phone_number": n.phone_number, "friendly_name": n.friendly_name, "sid": n.sid}
            for n in numbers
        ]
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao listar números da subconta {company.id}: {e}")
        return []


def configure_existing_number(company: Company, phone_number: str) -> bool:
    """Configura webhooks e salva um número que já existe na subconta."""
    if not company.twilio_subaccount_sid:
        return False
    creds = company.get_twilio_credentials()
    sub_client = Client(creds["account_sid"], creds["auth_token"])
    backend_url = os.getenv("PUBLIC_BASE_URL") or os.getenv("BASE_URL") or "http://localhost:5000"
    
    try:
        # 1. Busca o SID do número pelo valor
        numbers = sub_client.incoming_phone_numbers.list(phone_number=phone_number)
        if not numbers:
            logger.warning(f"[TWILIO] Número {phone_number} não encontrado na subconta {company.twilio_subaccount_sid}")
            return False
        
        number_sid = numbers[0].sid
        
        # 2. Atualiza os Webhooks
        sub_client.incoming_phone_numbers(number_sid).update(
            voice_url=f"{backend_url}/api/twilio/voice",
            voice_method="POST",
            status_callback=f"{backend_url}/api/twilio/status",
            status_callback_method="POST",
        )
        
        # 3. Salva no banco
        company.twilio_number = phone_number
        db.session.commit()
        return True
    except TwilioRestException as e:
        logger.error(f"[TWILIO] Erro ao configurar número existente {phone_number}: {e}")
        return False


def setup_full_company(company: Company, phone_number: str = None) -> dict:
    """
    Executa o setup completo de uma nova empresa (SaaS flow):
    1. Cria subconta
    2. Cria TwiML App
    3. Compra número de telefone (se phone_number for passado, compra ele)
    """
    results = {"ok": False, "steps": {}}

    try:
        # Passo 1: Subconta
        sub = create_subaccount(company)
        results["steps"]["subaccount"] = "ok"
        results["subaccount_sid"] = sub["subaccount_sid"]

        # Passo 2: TwiML App
        app_sid = create_twiml_app(company)
        results["steps"]["twiml_app"] = "ok" if app_sid else "failed"

        # Passo 3: Número
        number_result = provision_phone_number(company, area_code="11", specific_number=phone_number)
        if isinstance(number_result, dict) and "error" in number_result:
            results["steps"]["phone_number"] = "failed"
            results["error"] = number_result["error"]
            results["ok"] = False
            return results
            
        results["steps"]["phone_number"] = "ok"
        results["phone_number"] = number_result
        results["ok"] = True
        logger.info(f"[SETUP] Setup completo concluído para empresa {company.id}: {results}")

    except Exception as e:
        logger.error(f"[SETUP] Erro crítico no setup da empresa {company.id}: {e}")
        results["error"] = str(e)

    return results
