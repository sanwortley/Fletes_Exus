# backend/notifications.py

import os
import time
from typing import Dict
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException


from dotenv import load_dotenv
load_dotenv(override=True)

import requests
import urllib.parse

def send_whatsapp_ultramsg(text: str, to: str) -> Dict[str, str]:
    """
    Envía WhatsApp usando UltraMsg (API estable, requiere suscripción).
    """
    instance_id = os.getenv("ULTRAMSG_INSTANCE_ID")
    token = os.getenv("ULTRAMSG_TOKEN")

    if not instance_id or not token:
        print("[UltraMsg] ❌ Faltan credenciales (ULTRAMSG_INSTANCE_ID / ULTRAMSG_TOKEN)")
        return {"ok": "false", "error": "missing_credentials"}

    # Limpia el número (UltraMsg espera formato 549351...)
    to_clean = to.replace("whatsapp:", "").replace("+", "").replace(" ", "").strip()

    url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
    payload = {
        "token": token,
        "to": to_clean,
        "body": text
    }
    
    try:
        # UltraMsg usa request codificada como form-data o json
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        resp = requests.post(url, data=payload, headers=headers, timeout=10)
        data = resp.json()
        
        print(f"[UltraMsg] Respuesta: {data}")
        
        if data.get("sent") == "true" or "ok" in str(data.get("message", "")).lower():
            return {"ok": "true", "sid": str(data.get("id", "")), "provider": "ultramsg"}
            
        return {"ok": "false", "error": str(data), "provider": "ultramsg"}

    except Exception as e:
        print(f"[UltraMsg] Error: {e}")
        return {"ok": "false", "error": str(e), "provider": "ultramsg"}


def send_whatsapp_to_javier(text: str) -> Dict[str, str]:
    """
    Envía un WhatsApp a Javier usando el proveedor configurado (UltraMsg o Twilio).
    """
    provider = (os.getenv("WHATSAPP_PROVIDER") or "twilio").lower()
    w_to = (os.getenv("WHATSAPP_TO_JAVIER") or "").strip()

    # Opción 1: UltraMsg (Recomendado/Robusto)
    if provider == "ultramsg":
        return send_whatsapp_ultramsg(text, w_to)

    # Opción 2: Twilio (Fallback / Desarrollo)
    # ----------------------------------------
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    tok = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    w_from = (os.getenv("TWILIO_WHATSAPP_FROM") or "whatsapp:+14155238886").strip()

    # Normalizar para Twilio
    if w_from:
        w_from = w_from.replace(" ", "")
        if not w_from.startswith("whatsapp:"):
            w_from = "whatsapp:" + w_from
    
    # Asegurar formato Twilio para el destinatario
    w_to_twilio = w_to
    if w_to_twilio:
        w_to_twilio = w_to_twilio.replace(" ", "")
        if not w_to_twilio.startswith("whatsapp:"):
            w_to_twilio = "whatsapp:" + w_to_twilio

    if not (sid and tok and w_from and w_to_twilio):
        print(f"[Twilio] ❌ Faltan env vars.")
        return {"ok": "false", "error": "twilio_env_vars_missing"}

    try:
        cli = TwilioClient(sid, tok)
        msg = cli.messages.create(from_=w_from, to=w_to_twilio, body=text)
        print("[Twilio] ✅ Sent SID:", msg.sid)
        
        return {
            "ok": "true", 
            "sid": msg.sid, 
            "status": str(msg.status),
            "provider": "twilio"
        }

    except TwilioRestException as e:
        print(f"[Twilio] ⚠️ ERROR code={getattr(e,'code',None)} msg={e.msg}")
        return {"ok": "false", "code": str(getattr(e, "code", "")), "error": e.msg}
    except Exception as e:
        print("[Twilio] ⚠️ ERROR:", e)
        return {"ok": "false", "error": str(e)}
