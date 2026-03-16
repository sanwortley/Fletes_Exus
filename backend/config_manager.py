from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from sqlmodel import Session, select
from .models.models import dbPricingConfig
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Lista de variables que queremos permitir editar
EDITABLE_FIELDS = [
    "KM_POR_LITRO", "COSTO_LITRO", "COSTO_HORA", "COSTO_HORA_AYUDANTE",
    "FACTOR_PONDERACION", "FACTOR_TRAZADO", "VEL_KMH",
    "MANTENIMIENTO_POR_KM", "COSTO_PEAJE", "COSTO_CHOFER_HORA",
    "COSTO_ADMIN_HORA", "BASE_FIJA", "MIN_TOTAL", 
    "CARGA_DESC_H", "COSTO_COMBUSTIBLE_KM", "REDONDEO_MIN",
    "RETURN_TO_BASE_DEFAULT", "INCLUIR_CHOFER_ADMIN_EN_TOTAL", "MANTENIMIENTO_PCT"
]

class ConfigVars(BaseModel):
    KM_POR_LITRO: float = Field(default=8.0)
    COSTO_LITRO: float = Field(default=1600.0)
    COSTO_HORA: float = Field(default=25000.0)
    COSTO_HORA_AYUDANTE: float = Field(default=12000.0)
    FACTOR_PONDERACION: float = Field(default=1.5)
    FACTOR_TRAZADO: float = Field(default=1.25)
    VEL_KMH: float = Field(default=35.0)
    MANTENIMIENTO_POR_KM: float = Field(default=0.0)
    COSTO_PEAJE: float = Field(default=2000.0)
    COSTO_CHOFER_HORA: float = Field(default=7500.0)
    COSTO_ADMIN_HORA: float = Field(default=3500.0)
    BASE_FIJA: float = Field(default=0.0)
    MIN_TOTAL: float = Field(default=0.0)
    CARGA_DESC_H: float = Field(default=0.0)
    COSTO_COMBUSTIBLE_KM: float = Field(default=200.0)
    REDONDEO_MIN: int = Field(default=30)
    RETURN_TO_BASE_DEFAULT: bool = Field(default=False)
    INCLUIR_CHOFER_ADMIN_EN_TOTAL: bool = Field(default=False)
    MANTENIMIENTO_PCT: float = Field(default=0.20)

    model_config = {"populate_by_name": True, "extra": "ignore"}


def get_default_env_config() -> dict:
    """Lee los valores iniciales desde .env (fallback)"""
    return {
        "KM_POR_LITRO": float(os.getenv("KM_POR_LITRO", "8")),
        "COSTO_LITRO": float(os.getenv("COSTO_LITRO", "1600")),
        "COSTO_HORA": float(os.getenv("COSTO_HORA", "25000")),
        "COSTO_HORA_AYUDANTE": float(os.getenv("COSTO_HORA_AYUDANTE", "12000")),
        "FACTOR_PONDERACION": float(os.getenv("FACTOR_PONDERACION", "1.5")),
        "FACTOR_TRAZADO": float(os.getenv("FACTOR_TRAZADO", "1.25")),
        "VEL_KMH": float(os.getenv("VEL_KMH", "35")),
        "MANTENIMIENTO_POR_KM": float(os.getenv("MANTENIMIENTO_POR_KM", "0")),
        "COSTO_PEAJE": float(os.getenv("COSTO_PEAJE", "2000")),
        "COSTO_CHOFER_HORA": float(os.getenv("COSTO_CHOFER_HORA", "7500")),
        "COSTO_ADMIN_HORA": float(os.getenv("COSTO_ADMIN_HORA", "3500")),
        "BASE_FIJA": float(os.getenv("BASE_FIJA", "0")),
        "MIN_TOTAL": float(os.getenv("MIN_TOTAL", "0")),
        "CARGA_DESC_H": float(os.getenv("CARGA_DESC_H", "0")),
        "COSTO_COMBUSTIBLE_KM": float(os.getenv("COSTO_COMBUSTIBLE_KM", "200")),
        "REDONDEO_MIN": int(os.getenv("REDONDEO_MIN", "30")),
        "RETURN_TO_BASE_DEFAULT": (os.getenv("RETURN_TO_BASE_DEFAULT", "0") == "1"),
        "INCLUIR_CHOFER_ADMIN_EN_TOTAL": (os.getenv("INCLUIR_CHOFER_ADMIN_EN_TOTAL", "0") == "1"),
        "MANTENIMIENTO_PCT": float(os.getenv("MANTENIMIENTO_PCT", "0.20")),
    }

class DynamicConfig:
    @classmethod
    def get_values(cls, db_session: Session) -> dict:
        """Lee la configuración desde la tabla PricingConfig."""
        try:
            # En el refactor, db_session será el objeto Session de SQLModel
            statement = select(dbPricingConfig).where(dbPricingConfig.id == "pricing_vars")
            config = db_session.exec(statement).first()
            
            defaults = get_default_env_config()
            if config and config.config_data:
                # Merge con lo que hay en DB
                defaults.update({k: v for k, v in config.config_data.items() if k in defaults})
            return defaults
        except Exception as e:
            print(f"Error reading dynamic config from SQL: {e}")
            return get_default_env_config()

    @classmethod
    def update_values(cls, db_session: Session, new_values: dict):
        # Validar con Pydantic
        validated_data = ConfigVars(**new_values).model_dump()
        
        statement = select(dbPricingConfig).where(dbPricingConfig.id == "pricing_vars")
        config = db_session.exec(statement).first()
        
        if config:
            config.config_data = validated_data
            config.updated_at = datetime.now(timezone.utc)
        else:
            config = dbPricingConfig(id="pricing_vars", config_data=validated_data)
            db_session.add(config)
        
        db_session.commit()
        db_session.refresh(config)
        return validated_data
