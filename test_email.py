# test_email.py
import os
from dotenv import load_dotenv
from backend.notifications import send_email_to_admin

# Cargar variables de entorno
load_dotenv(override=True)

def test():
    print("--- 📧 Iniciando prueba de envío de Email ---")
    
    subject = "Prueba de Sistema - Fletes Javier"
    body_text = "Esto es una prueba del sistema de notificaciones por correo."
    body_html = "<h1>Prueba de Sistema</h1><p>Esto es una prueba del sistema de <strong>notificaciones por correo</strong>.</p>"
    
    res = send_email_to_admin(subject, body_text, body_html)
    
    if res.get("ok") == "true":
        print(f"✅ ÉXITO: El mail debería haber llegado a: {res.get('recipients')}")
    else:
        print(f"❌ ERROR: {res.get('error')}")
        print("\nConsejo: Si el error es de autenticación, asegurate de que la 'SMTP_PASS' sea una 'Contraseña de Aplicación' de Google y no tu contraseña normal.")

if __name__ == "__main__":
    test()
