import os, re, smtplib, ssl, traceback
from typing import Optional, Dict, List
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# =========== WhatsApp (Twilio) ===========
from twilio.rest import Client as TwilioClient

def send_whatsapp_to_javier(text: str) -> Dict[str, str]:
    try:
        sid    = os.getenv("TWILIO_ACCOUNT_SID")
        tok    = os.getenv("TWILIO_AUTH_TOKEN")
        w_from = os.getenv("TWILIO_WHATSAPP_FROM")   # whatsapp:+14155238886
        w_to   = os.getenv("WHATSAPP_TO_JAVIER")     # whatsapp:+549351...

        if not all([sid, tok, w_from, w_to]):
            print("[WhatsApp] Variables faltantes.")
            return {"ok": "false", "error": "twilio_env_vars_missing"}

        client = TwilioClient(sid, tok)
        msg = client.messages.create(from_=w_from, to=w_to, body=text)
        print(f"[WhatsApp] Enviado → SID: {msg.sid}")
        return {"ok": "true", "sid": msg.sid}
    except Exception as e:
        print(f"[WhatsApp] Error: {e}")
        return {"ok": "false", "error": str(e)}

# === helpers ===
def _parse_recipients(raw: str) -> List[str]:
    # extrae emails válidos e ignora comas, espacios y basura (////)
    recips = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw or "")
    return list(dict.fromkeys([r.strip() for r in recips]))  # únicos y limpiados

# =========== Email (SMTP Gmail) ===========
def _smtp_send(subject: str, html: str) -> str:
    host   = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port   = int(os.getenv("SMTP_PORT", "587"))
    user   = os.getenv("SMTP_USER")
    pwd    = os.getenv("SMTP_PASS")
    raw_to = os.getenv("EMAIL_TO_JAVIER", "")

    recipients = _parse_recipients(raw_to)
    if not recipients:
        recipients = [user]  # fallback
    email_from = user  # Gmail exige From = usuario autenticado

    print(f"[SMTP] To parsed -> {recipients}")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=20) as s:
        s.set_debuglevel(1)
        s.starttls(context=ctx)
        s.login(user, pwd)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_from
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html, "html"))

        s.sendmail(email_from, recipients, msg.as_string())
        print(f"[SMTP] Enviado a: {', '.join(recipients)}")
    return "OK"

# ☑️ Mantengo la firma antigua para que el backend no rompa
def send_email_smtp(subject: str, html: str) -> str:
    try:
        return _smtp_send(subject, html)
    except Exception as e:
        print("[SMTP] Error:", e)
        traceback.print_exc()
        raise

# =========== Email (SendGrid) ===========
def send_email_sendgrid(subject: str, html: str, to_email: Optional[str] = None) -> Dict[str, str]:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        api_key   = os.getenv("SENDGRID_API_KEY")
        email_from = os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER")
        fallback   = os.getenv("EMAIL_TO_JAVIER")
        email_to   = to_email or fallback

        if not all([api_key, email_from, email_to]):
            raise ValueError("Faltan variables de entorno SendGrid")

        # también soporta múltiples destinatarios:
        recipients = _parse_recipients(email_to)
        message = Mail(from_email=email_from, to_emails=recipients, subject=subject, html_content=html)

        print(f"[SendGrid] Enviando a: {', '.join(recipients)}")
        sg = SendGridAPIClient(api_key)
        resp = sg.send(message)
        print(f"[SendGrid] Código: {resp.status_code}")
        return {"ok": "true", "status": str(resp.status_code)}
    except Exception as e:
        print("[SendGrid] Error:", e)
        traceback.print_exc()
        return {"ok": "false", "error": str(e)}

# =========== Envío unificado ===========
def send_email(subject: str, html: str):
    # intenta SMTP y, si falla, cae a SendGrid
    try:
        return _smtp_send(subject, html)
    except Exception as e:
        print(f"[Email] Falla SMTP: {e} — probando SendGrid.")
        return send_email_sendgrid(subject, html)
