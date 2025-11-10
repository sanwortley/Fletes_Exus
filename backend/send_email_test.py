# send_email_test.py
import os
from dotenv import load_dotenv, find_dotenv
from backend.notifications import send_email_smtp

env_path = find_dotenv(filename=".env", usecwd=True)
load_dotenv(env_path, override=True)   # <- clave
print("Using .env:", env_path)
print("SMTP_USER:", os.getenv("SMTP_USER"))
print("EMAIL_TO_JAVIER (raw):", repr(os.getenv("EMAIL_TO_JAVIER")))

html = """
  <h2>Mail de prueba desde Exus</h2>
  <p>Envío SMTP múltiple (Gmail App Password) ✔️</p>
"""
res = send_email_smtp("🧾 Prueba notificación - Fletes Javier", html)
print("Resultado:", res)
