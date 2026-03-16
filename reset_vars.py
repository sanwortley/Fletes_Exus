import os
import sys
from sqlmodel import Session, select
from dotenv import load_dotenv

# Añadimos el directorio actual al path para importar los modelos
sys.path.append(os.path.join(os.getcwd(), "backend"))
from models.models import dbPricingConfig
from database import engine

load_dotenv()

def reset_vars():
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

    with Session(engine) as session:
        statement = select(dbPricingConfig).where(dbPricingConfig.id == "pricing_vars")
        pcfg = session.exec(statement).first()
        if pcfg:
            pcfg.config_data = reset_values
        else:
            pcfg = dbPricingConfig(id="pricing_vars", config_data=reset_values)
            session.add(pcfg)
        session.commit()

    print("✅ Todas las variables de configuración han sido reseteadas a 0 en la base de datos SQL.")

if __name__ == "__main__":
    reset_vars()
