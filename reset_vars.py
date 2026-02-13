
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.get_database()

# Definimos todos los campos en 0 o sus valores mínimos lógicos
reset_values = {
    "KM_POR_LITRO": 0.0,
    "COSTO_LITRO": 0.0,
    "COSTO_HORA": 0.0,
    "COSTO_HORA_AYUDANTE": 0.0,
    "FACTOR_PONDERACION": 0.0,
    "FACTOR_TRAZADO": 0.0,
    "VEL_KMH": 0.0,
    "MANTENIMIENTO_POR_KM": 0.0,
    "COSTO_PEAJE": 0.0,
    "COSTO_CHOFER_HORA": 0.0,
    "COSTO_ADMIN_HORA": 0.0,
    "BASE_FIJA": 0.0,
    "MIN_TOTAL": 0.0,
    "CARGA_DESC_H": 0.0,
    "COSTO_COMBUSTIBLE_KM": 0.0,
    "REDONDEO_MIN": 0,
    "MANTENIMIENTO_PCT": 0.0,
    # Boqueanos: los dejamos en False
    "INCLUIR_AYUDANTE_EN_TOTAL": False,
    "RETURN_TO_BASE_DEFAULT": False,
    "EXCEL_MODE": False,
    "INCLUIR_CHOFER_ADMIN_EN_TOTAL": False
}

db.config.update_one(
    {"_id": "pricing_vars"},
    {"$set": reset_values},
    upsert=True
)

print("✅ Todas las variables de configuración han sido reseteadas a 0 en la base de datos.")
