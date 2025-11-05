# notifications.py
import os
from typing import Optional

# WhatsApp (Twilio)
from twilio.rest import Client as TwilioClient

def send_whatsapp_to_javier(text: str) -> Optional[str]:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    tok = os.getenv("TWILIO_AUTH_TOKEN")
    w_from = os.getenv("TWILIO_WHATSAPP_FROM")
    w_to = os.getenv("WHATSAPP_TO_JAVIER")
    if not all([sid, tok, w_from, w_to]):
        return "Twilio env vars faltantes"
    client = TwilioClient(sid, tok)
    msg = client.messages.create(from_=w_from, to=w_to, body=text)
    return msg.sid

# Email (SendGrid recomendado)
def send_email_sendgrid(subject: str, html: str) -> Optional[str]:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    api_key = os.getenv("SENDGRID_API_KEY")
    email_from = os.getenv("EMAIL_FROM")
    email_to = os.getenv("EMAIL_TO_JAVIER")
    if not all([api_key, email_from, email_to]):
        return "SendGrid env vars faltantes"
    message = Mail(from_email=email_from, to_emails=email_to, subject=subject, html_content=html)
    sg = SendGridAPIClient(api_key)
    resp = sg.send(message)
    return f"sendgrid_status={resp.status_code}"

# Email (SMTP Gmail alternativa)
def send_email_smtp(subject: str, html: str) -> Optional[str]:
    import smtplib, ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM")
    email_to   = os.getenv("EMAIL_TO_JAVIER")
    if not all([host, port, user, pwd, email_from, email_to]):
        return "SMTP env vars faltantes"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.attach(MIMEText(html, "html"))
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, pwd)
        server.sendmail(email_from, [email_to], msg.as_string())
    return "smtp_ok"
