import os

file_path = r"c:\Users\Allan\nexdial\app\api\routes\twilio_voice.py"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

find_text = """        callsid_valid = (stored_call_sid and db_call_sid and stored_call_sid == db_call_sid)
        
        # Se ja temos ctz que e humano OU ja nao esta mais tocando, promovemos
        if auto_promote and (not is_ringing or not amd_uncertain) and callsid_valid:"""

replace_text = """        callsid_valid = (stored_call_sid and db_call_sid and stored_call_sid == db_call_sid)
        if not callsid_valid:
            logger.info("[PENDING] CallSid divergente (ignorado): stored=%s db=%s", stored_call_sid, db_call_sid)
        
        # Se ja temos ctz que e humano OU ja nao esta mais tocando, promovemos
        if auto_promote and (not is_ringing or not amd_uncertain):"""

text = text.replace(find_text, replace_text)

find_elif = """            if conf_name_val.startswith("agent_bridge_") and item.get("agent_leg_call_sid"):
                item["audio_bridged"] = True
            logger.info(
                "[PENDING] Timer (450ms) concluido - promovendo conference=%s para answered_waiting_agent",
                conf_name_val,
            )
        elif not callsid_valid:
            logger.info("[PENDING] CallSid Guard bloqueou promocao: stored=%s db=%s", stored_call_sid, db_call_sid)
            return jsonify({
                "has_call": True,
                "show_popup": False,
                "status": "awaiting_confirmation",
                "status_display": _call_status_display("awaiting_confirmation"),
                "lead_id": item.get("lead_id"),
                "conference_name": item.get("conference_name"),
            }), 200"""

replace_elif = """            if conf_name_val.startswith("agent_bridge_") and item.get("agent_leg_call_sid"):
                item["audio_bridged"] = True
            logger.info(
                "[PENDING] Timer (450ms) concluido - promovendo conference=%s para answered_waiting_agent",
                conf_name_val,
            )"""

# Fallback in case of `-` vs `—` (em-dash vs hyphen)
find_elif_2 = find_elif.replace("concluido - promovendo", "concluido — promovendo")
replace_elif_2 = replace_elif.replace("concluido - promovendo", "concluido — promovendo")

if find_elif in text:
    text = text.replace(find_elif, replace_elif)
elif find_elif_2 in text:
    text = text.replace(find_elif_2, replace_elif_2)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Patch applied for CallSid relaxation.")
