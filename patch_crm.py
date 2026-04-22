import re

# Função que será injetada
crm_status_func = '''
def update_lead_crm_status(lead_id, call_id, final_status, reason=""):
    """
    Centraliza a classificação do Lead e Call, garantindo regras estritas e logs.
    final_status DEVE ser: "answered", "voicemail", "no_answer", "failed"
    """
    if not lead_id:
        return

    from app.extensions import db
    from app.models.call import Call
    from app.models.lead import Lead
    from app.api.utils.crm_utils import move_lead_to_stage
    import logging
    logger = logging.getLogger(__name__)

    lead = Lead.query.get(lead_id)
    if not lead:
        return

    # Mapeamento do Status pro PIPELINE
    stage_map = {
        "voicemail": "Caixa Postal",
        "no_answer": "Não Atendeu",
        "answered": "Em Contato",
        "failed": "Erro"
    }
    
    stage = stage_map.get(final_status)
    
    # 1. Atualizar o Call
    if call_id:
        call = Call.query.get(call_id)
        if call:
            call.status = final_status
            call.disposition = reason
            
            # Se já está como caixa postal, e tentar sobrescrever com no_answer, bloquear
            # Regra: Voicemail > Answered > No Answer > Failed
            # Neste helper focamos em atualizar direto mas podemos adicionar lógica futuramente.
            
    # 2. Atualizar o Lead
    lead.status = final_status
    
    logger.info(f"[CRM] Lead {lead_id} -> {final_status} ({stage}) | Motivo: {reason}")
    db.session.commit()
    
    # 3. Mover no funil
    if stage:
        move_lead_to_stage(lead_id, stage)


'''

with open('c:/Users/Allan/nexdial/app/api/routes/twilio_voice.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Injunte a função após a declaração do Blueprint
if "def update_lead_crm_status" not in content:
    content = content.replace('twilio_voice_bp = Blueprint("twilio_voice", __name__, url_prefix="/api/twilio")', 
                             'twilio_voice_bp = Blueprint("twilio_voice", __name__, url_prefix="/api/twilio")\n' + crm_status_func)


# === 1. `/status` endpoint ===
# Atualmente ele tem:
# if call.status not in ["completed"]: call.status = call_status
# lead.status = ... move_lead_to_stage()
# Nós o substituímos pelo nosso helper
status_block_start = r'if call:'
status_block_end = r'# --- Retomar Discador Cauteloso ---'

new_status_block = '''if call:
        if call.status not in ["completed"]:
            call.status = call_status

        if not getattr(call, "answered_at", None) and call_status in ("completed",):
             pass # não faz nada de timing
        if not getattr(call, "ended_at", None) and call_status in ("completed", "busy", "failed", "no-answer", "canceled"):
             call.ended_at = datetime.utcnow()
        db.session.commit()

        # Atualizar status CRM 
        if call_status in ("busy", "failed", "canceled"):
            update_lead_crm_status(call.lead_id, call.id, "failed", f"Erro Telecom: {call_status}")
        elif call_status == "no-answer":
            update_lead_crm_status(call.lead_id, call.id, "no_answer", "Nao atendeu (Ring Timeout)")
            
    # --- Retomar Discador Cauteloso ---'''

# Expressão regular cuidadosa
# Queremos focar só em substituir a parte dentro do if call
# Como o código lá é longo, vamos substituir a partir de `if call:` até `# --- Retomar`
content = re.sub(r'if call:.*?(?=# --- Retomar Discador Cauteloso ---)', new_status_block + "\n    ", content, flags=re.DOTALL)


# === 2. `conference-events` (participant-leave) ===
# No participant-leave, ele checa amd_already_dispositioned

conf_block_start = r'lead_id = call\.lead_id.*?if lead_id and not amd_already_dispositioned:'
# Vamos achar todo o bloco do `if lead_id and not amd_already_dispositioned:`

def replace_conf_block(match):
    return '''lead_id = call.lead_id
                if lead_id and not amd_already_dispositioned:
                    # AMD nao interveio — usar resultado da conferencia
                    if conference_was_answered:
                        # Agente falou com o lead -> "Em Contato"
                        update_lead_crm_status(lead_id, call.id, "answered", "Operador interagiu na ponte")
                    elif lead_did_answer:
                        # Lead atendeu mas agente nao entrou a tempo -> "Nao Atendeu"
                        update_lead_crm_status(lead_id, call.id, "no_answer", "Desligou antes do pop-up/operador")
                    else:
                        # Lead nao chegou a atender (busy/failed tratado pelo /status)
                        update_lead_crm_status(lead_id, call.id, "no_answer", "Caiu sem interacao")

                # ---'''

content = re.sub(r'lead_id = call\.lead_id\s+if lead_id and not amd_already_dispositioned:.*?(?=# --- Se for um retorno agendado)', replace_conf_block, content, flags=re.DOTALL)


# === 3. `amd_callback` ===
# Na máquina:
# call.status = "voicemail"
# move_lead_to_stage(lead_id, "Caixa Postal")
def replace_amd_machine(match):
    return '''# Avisa memoria que maquina derrubou
        if conf_item:
            conf_item["status"] = "machine_dropped"

        if call:
            update_lead_crm_status(call.lead_id, call.id, "voicemail", f"AMD: {answered_by}")

        try:'''

content = re.sub(r'# Avisa memoria que maquina derrubou.*?try:', replace_amd_machine, content, flags=re.DOTALL)


def replace_amd_unknown(match):
    return '''# Avisa memoria que maquina derrubou
        if conf_item:
            conf_item["status"] = "machine_dropped"

        if call:
            update_lead_crm_status(call.lead_id, call.id, "no_answer", "AMD: Unknown (Excedeu 8s silencioso)")

        try:'''

content = re.sub(r'# Excedeu timeout de silencio ou falhou.*?# Avisa memoria que maquina derrubou.*?try:', '# Excedeu timeout de silencio ou falhou\n        logger.info("[AMD] Status UNKNOWN/Falha | CallSid=%s → Forçando DROP no_answer", call_sid)\n        ' + replace_amd_unknown(None), content, flags=re.DOTALL)


with open('c:/Users/Allan/nexdial/app/api/routes/twilio_voice.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Script concluido com sucesso!")
