from backend.notifications import send_whatsapp_to_javier
import os

# Forzar credenciales del env actual por si acaso, aunque notifications usa load_dotenv
print("Probando envío de WhatsApp...")
res = send_whatsapp_to_javier("Hola Javier, esto es una prueba de diagnóstico del sistema.")
print("Resultado:", res)
