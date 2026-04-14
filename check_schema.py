import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

connect_args = {} if not DATABASE_URL.startswith("sqlite") else {"check_same_thread": False}

from sqlmodel import create_engine, inspect

engine = create_engine(DATABASE_URL, connect_args=connect_args)
inspector = inspect(engine)

MODEL_FIELDS = {
    "quotes": [
        "id", "mongo_id", "nombre_cliente", "telefono", "tipo_carga",
        "origen", "origen_lat", "origen_lng", "destino", "destino_lat", "destino_lng",
        "fecha", "ayudante", "regreso_base", "hora_inicio", "hora_fin", "horas_reales",
        "peajes", "viaticos", "accepted_terms", "accepted_terms_at",
        "fecha_turno", "hora_turno",
        "dist_km", "tiempo_viaje_min", "tiempo_servicio_min", "monto_estimado",
        "horas_base", "costo_tiempo_base", "mantenimiento", "costo_tiempo",
        "costo_combustible", "peajes_total", "costo_ayudante", 
        "costo_chofer_parcial", "costo_admin_parcial",
        "tramo_base_origen_km", "tramo_origen_destino_km", "tramo_destino_base_km",
        "tramo_base_origen_min", "tramo_origen_destino_min", "tramo_destino_base_min",
        "extra_servicio_min",
        "estado", "confirmado_en", "sent_at", "cancelled_at", 
        "completed_at", "voided_at", "fecha_hora_preferida", "notas_confirmacion",
        "is_deleted", "created_at"
    ],
    "users": [
        "id", "username", "email", "password_hash", "role",
        "failed_logins", "lock_until", "mongo_id", "created_at", "updated_at"
    ],
    "bookings": [
        "id", "date", "time", "quote_id", "status", "confirmed_at", "created_at"
    ],
    "availability_overrides": [
        "id", "date", "enabled", "slots", "updated_at"
    ],
    "block_rules": [
        "id", "hour_from", "hour_to", "apply_all", 
        "date_from", "date_to", "label", "created_at"
    ],
    "global_configs": [
        "id", "blocks_enabled", "updated_at"
    ],
    "pricing_configs": [
        "id", "config_data", "updated_at"
    ],
    "audit_logs": [
        "id", "quote_id", "action", "details", "admin_user", "created_at"
    ],
}

def check_table(table_name):
    print(f"\n{'='*60}")
    print(f"TABLE: {table_name}")
    print(f"{'='*60}")
    
    try:
        db_columns = inspector.get_columns(table_name)
        db_cols_set = {c["name"] for c in db_columns}
        model_cols_set = set(MODEL_FIELDS.get(table_name, []))
        
        missing_in_db = model_cols_set - db_cols_set
        extra_in_db = db_cols_set - model_cols_set
        
        if missing_in_db:
            print(f"  [MISSING] FALTAN en DB ({len(missing_in_db)}):")
            for col in sorted(missing_in_db):
                print(f"     - {col}")
        else:
            print(f"  [OK] Sin columnas faltantes")
            
        if extra_in_db:
            print(f"  ⚠️ EXTRA en DB ({len(extra_in_db)}):")
            for col in sorted(extra_in_db):
                print(f"     + {col}")
                
    except Exception as e:
        print(f"  ❌ ERROR: {e}")

def main():
    print("=== CHECK SCHEMA: modelo vs DB ===")
    print(f"URL: {DATABASE_URL}")
    
    tables = inspector.get_table_names()
    print(f"\nTablas en DB: {tables}")
    
    for table in MODEL_FIELDS:
        if table in tables:
            check_table(table)
        else:
            print(f"\n{'='*60}")
            print(f"TABLE: {table} - ❌ NO EXISTE EN DB")
            print(f"{'='*60}")
    
    print(f"\n{'='*60}")
    print("RESUMEN")
    print(f"{'='*60}")
    print("""
CÓMO AGREGAR COLUMNAS FALTANTES EN PostgreSQL:

ALTER TABLE quotes ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE quotes ADD COLUMN voided_at TIMESTAMP;
ALTER TABLE quotes ADD COLUMN notas_confirmacion TEXT;
ALTER TABLE quotes ADD COLUMN fecha_hora_preferida TEXT;

# Para users
ALTER TABLE users ADD COLUMN failed_logins INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN lock_until TIMESTAMP;
""")

if __name__ == "__main__":
    main()