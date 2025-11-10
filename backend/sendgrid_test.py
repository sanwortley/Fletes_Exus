# sendgrid_test.py
import os, certifi, sys
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

print("Usando CA bundle:", certifi.where())

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

API_KEY = os.getenv("SENDGRID_API_KEY")  # ponelo en tu .env/entorno
if not API_KEY:
    print("Falta SENDGRID_API_KEY")
    sys.exit(1)

message = Mail(
    from_email=os.getenv("EMAIL_FROM", "no-reply@tu-dominio.com"),
    to_emails=os.getenv("EMAIL_TO_JAVIER", "fletesjavier@gmail.com"),
    subject="Prueba SendGrid ✅",
    html_content="<strong>Hola Javier, mail de prueba.</strong>",
)

try:
    sg = SendGridAPIClient(API_KEY)
    resp = sg.send(message)
    print("Status:", resp.status_code)
except Exception as e:
    print("Error:", e)
