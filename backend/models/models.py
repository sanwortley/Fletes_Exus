from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlmodel import SQLModel, Field, JSON
import uuid

# --- Modelos Basados en el Proyecto Exus ---

class dbUser(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    role: str = "admin"
    failed_logins: int = Field(default=0)
    lock_until: Optional[datetime] = None
    mongo_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class dbQuote(SQLModel, table=True):
    __tablename__ = "quotes"
    id: Optional[int] = Field(default=None, primary_key=True)
    mongo_id: Optional[str] = Field(default=None, index=True) # Para la trazabilidad de migración
    nombre_cliente: str
    telefono: str
    tipo_carga: str
    origen: str
    origen_lat: Optional[float] = None
    origen_lng: Optional[float] = None
    destino: str
    destino_lat: Optional[float] = None
    destino_lng: Optional[float] = None
    fecha: Optional[str] = None # Fecha sugerida por el usuario
    ayudante: bool = Field(default=False)
    regreso_base: bool = Field(default=True)
    hora_inicio: Optional[str] = None
    hora_fin: Optional[str] = None
    horas_reales: Optional[float] = None
    peajes: int = Field(default=0)
    viaticos: float = Field(default=0.0)
    accepted_terms: bool = Field(default=False)
    accepted_terms_at: Optional[datetime] = None
    
    # Turno
    fecha_turno: Optional[str] = None # YYYY-MM-DD
    hora_turno: Optional[str] = None  # HH:MM

    # Totales calculados
    dist_km: float = Field(default=0.0)
    tiempo_viaje_min: int = Field(default=0)
    tiempo_servicio_min: int = Field(default=0)
    monto_estimado: float = Field(default=0.0)
    
    # Desgloses y tramos
    horas_base: float = Field(default=0.0)
    costo_tiempo_base: float = Field(default=0.0)
    mantenimiento: float = Field(default=0.0)
    costo_tiempo: float = Field(default=0.0)
    costo_combustible: float = Field(default=0.0)
    peajes_total: float = Field(default=0.0)
    costo_ayudante: float = Field(default=0.0)
    costo_chofer_parcial: float = Field(default=0.0)
    costo_admin_parcial: float = Field(default=0.0)
    
    tramo_base_origen_km: float = Field(default=0.0)
    tramo_origen_destino_km: float = Field(default=0.0)
    tramo_destino_base_km: float = Field(default=0.0)
    tramo_base_origen_min: int = Field(default=0)
    tramo_origen_destino_min: int = Field(default=0)
    tramo_destino_base_min: int = Field(default=0)
    extra_servicio_min: int = Field(default=0)

    # Estado y Tiempos
    estado: str = Field(default="preview", index=True) # preview, sent, confirmado, realizado, rechazado, cancelado, anulado
    confirmado_en: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    voided_at: Optional[datetime] = None
    fecha_hora_preferida: Optional[str] = None
    notas_confirmacion: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class dbBooking(SQLModel, table=True):
    __tablename__ = "bookings"
    id: Optional[int] = Field(default=None, primary_key=True)
    date: str = Field(index=True) # YYYY-MM-DD
    time: str = Field(index=True) # HH:MM
    quote_id: Optional[str] = Field(default=None) # Guardamos como string por flexibilidad/compatibilidad
    status: str = Field(default="reserved") # reserved, confirmed, cancelled, completed
    confirmed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class dbAvailabilityOverride(SQLModel, table=True):
    __tablename__ = "availability_overrides"
    id: Optional[int] = Field(default=None, primary_key=True)
    date: str = Field(index=True, unique=True)
    enabled: bool = Field(default=True)
    slots: List[str] = Field(default_factory=list, sa_type=JSON) # Lista de strings
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class dbBlockRule(SQLModel, table=True):
    __tablename__ = "block_rules"
    id: Optional[int] = Field(default=None, primary_key=True)
    hour_from: str
    hour_to: str
    apply_all: bool = Field(default=False)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    label: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class dbGlobalConfig(SQLModel, table=True):
    __tablename__ = "global_configs"
    id: str = Field(primary_key=True, default="global_config")
    blocks_enabled: bool = Field(default=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class dbPricingConfig(SQLModel, table=True):
    __tablename__ = "pricing_configs"
    id: str = Field(primary_key=True, default="pricing_vars")
    config_data: Dict[str, float] = Field(default_factory=dict, sa_type=JSON)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
