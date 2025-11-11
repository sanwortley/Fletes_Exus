# backend/notifications.py
import os
import time
from typing import Dict
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException


def send_whatsapp_to_javier(text: str) -> Dict[str, str]:
    """
    Envía un WhatsApp a Javier usando Twilio (sandbox o número verificado).
    Devuelve: {"ok": "true"/"false", "sid": str, "status": str, "code": str, "message": str}
    """
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    tok = os.getenv("TWILIO_AUTH_TOKEN")
    w_from = (os.getenv("TWILIO_WHATSAPP_FROM") or "whatsapp:+14155238886").strip()
    w_to = (os.getenv("WHATSAPP_TO_JAVIER") or "").strip()

    # Normalizar prefijos (Twilio exige "whatsapp:")
    if w_from and not w_from.startswith("whatsapp:"):
        w_from = "whatsapp:" + w_from.replace(" ", "")
    if w_to and not w_to.startswith("whatsapp:"):
        w_to = "whatsapp:" + w_to.replace(" ", "")

    if not (sid and tok and w_from and w_to):
        print("[Twilio] ❌ Faltan env vars (TWILIO_* / WHATSAPP_TO_JAVIER).")
        return {"ok": "false", "error": "twilio_env_vars_missing"}

    try:
        cli = TwilioClient(sid, tok)
        msg = cli.messages.create(from_=w_from, to=w_to, body=text)
        print("[Twilio] ✅ created SID:", msg.sid, "status:", msg.status)

        # Poll ~10s (5 intentos cada 2s) para conocer estado final
        m = None
        for _ in range(5):
            time.sleep(2)
            m = cli.messages(msg.sid).fetch()
            print("[Twilio] poll ->", m.status, "code:", m.error_code, "msg:", m.error_message)
            if m.status in ("delivered", "failed", "undelivered"):
                break
        if m is None:
            m = msg

        return {
            "ok": "true" if (getattr(m, "error_code", None) is None and str(m.status) in ("sent", "delivered", "read")) else "false",
            "sid": msg.sid,
            "status": str(m.status),
            "code": "" if getattr(m, "error_code", None) is None else str(m.error_code),
            "message": "" if getattr(m, "error_message", None) is None else str(m.error_message),
        }

    except TwilioRestException as e:
        print(f"[Twilio] ⚠️ ERROR code={getattr(e,'code',None)} msg={e.msg}")
        return {"ok": "false", "code": str(getattr(e, "code", "")), "error": e.msg}
    except Exception as e:
        print("[Twilio] ⚠️ ERROR:", e)
        return {"ok": "false", "error": str(e)}
