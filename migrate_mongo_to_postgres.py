import os
import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from sqlmodel import Session, create_engine, select, SQLModel
from dotenv import load_dotenv

# Añadimos el directorio actual al path para importar los modelos
sys.path.append(os.path.join(os.getcwd(), "backend"))
from models.models import (
    dbUser, dbQuote, dbBooking, dbAvailabilityOverride, 
    dbBlockRule, dbGlobalConfig, dbPricingConfig
)
from database import engine

# Configuración
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "fletes_db" # Según el URI en el .env

def migrate():
    # 1. Conexión a MongoDB
    print(f"--- Conectando a MongoDB: {MONGO_URI} ---")
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[DB_NAME]

    # 2. Inicializar base de datos SQL
    print("--- Inicializando base de datos SQL ---")
    SQLModel.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        # --- MIGRAR USUARIOS ---
        print("Migrando usuarios...")
        mongo_users = list(mongo_db["users"].find())
        for u in mongo_users:
            # Evitar duplicados por email o username
            exists = session.exec(select(dbUser).where(dbUser.email == u.get("email"))).first()
            if not exists:
                user = dbUser(
                    mongo_id=str(u["_id"]),
                    username=u.get("username") or u.get("email"),
                    email=u.get("email"),
                    password_hash=u.get("password_hash"),
                    role=u.get("role", "admin"),
                    failed_logins=u.get("failed_logins") or u.get("failed_attempts", 0),
                    lock_until=u.get("lock_until") or u.get("last_fail"),
                    created_at=u.get("created_at") or datetime.now(timezone.utc)
                )
                session.add(user)
        session.commit()

        # --- MIGRAR REGLAS DE BLOQUEO ---
        print("Migrando reglas de bloqueo...")
        mongo_rules = list(mongo_db["block_rules"].find())
        for r in mongo_rules:
            rule = dbBlockRule(
                hour_from=r.get("hour_from"),
                hour_to=r.get("hour_to"),
                apply_all=r.get("apply_all", False),
                date_from=r.get("date_from"),
                date_to=r.get("date_to"),
                label=r.get("label"),
                created_at=r.get("created_at") or datetime.now(timezone.utc)
            )
            session.add(rule)
        
        # --- CONFIGURACIÓN GLOBAL ---
        print("Migrando configuración global...")
        mongo_cfg = mongo_db["block_config"].find_one({"_id": "global_config"}) or mongo_db["block_config"].find_one({})
        if mongo_cfg:
            cfg = dbGlobalConfig(
                id="global_config",
                blocks_enabled=mongo_cfg.get("blocks_enabled", True),
                updated_at=mongo_cfg.get("updated_at") or datetime.now(timezone.utc)
            )
            session.merge(cfg)
        session.commit()

        # --- OVERRIDES DE DISPONIBILIDAD ---
        print("Migrando overrides de disponibilidad...")
        mongo_av = list(mongo_db["availability"].find())
        for av in mongo_av:
            ovr = dbAvailabilityOverride(
                date=av.get("date"),
                enabled=av.get("enabled", True),
                slots=av.get("slots", []),
                updated_at=av.get("updated_at") or datetime.now(timezone.utc)
            )
            session.add(ovr)
        session.commit()

        # --- PRESUPUESTOS (QUOTES) ---
        print("Migrando presupuestos (esto puede tardar)...")
        mongo_quotes = list(mongo_db["quotes"].find())
        quote_map = {} # mongo_id -> sql_id
        for q in mongo_quotes:
            quote = dbQuote(
                mongo_id=str(q["_id"]),
                nombre_cliente=q.get("nombre_cliente"),
                telefono=q.get("telefono"),
                tipo_carga=q.get("tipo_carga"),
                origen=q.get("origen"),
                origen_lat=q.get("origen_lat"),
                origen_lng=q.get("origen_lng"),
                destino=q.get("destino"),
                destino_lat=q.get("destino_lat"),
                destino_lng=q.get("destino_lng"),
                fecha=q.get("fecha"),
                ayudante=q.get("ayudante", False),
                regreso_base=q.get("regreso_base", True),
                hora_inicio=q.get("hora_inicio"),
                hora_fin=q.get("hora_fin"),
                horas_reales=q.get("horas_reales"),
                peajes=q.get("peajes", 0),
                viaticos=q.get("viaticos", 0.0),
                accepted_terms=q.get("accepted_terms", False),
                accepted_terms_at=q.get("accepted_terms_at"),
                fecha_turno=q.get("fecha_turno"),
                hora_turno=q.get("hora_turno"),
                dist_km=q.get("dist_km", 0.0),
                tiempo_viaje_min=q.get("tiempo_viaje_min", 0),
                tiempo_servicio_min=q.get("tiempo_servicio_min", 0),
                monto_estimado=q.get("monto_estimado", 0.0),
                horas_base=q.get("horas_base", 0.0),
                costo_tiempo_base=q.get("costo_tiempo_base", 0.0),
                mantenimiento=q.get("mantenimiento", 0.0),
                costo_tiempo=q.get("costo_tiempo", 0.0),
                costo_combustible=q.get("costo_combustible", 0.0),
                peajes_total=q.get("peajes_total", 0.0),
                costo_ayudante=q.get("costo_ayudante", 0.0),
                costo_chofer_parcial=q.get("costo_chofer_parcial", 0.0),
                costo_admin_parcial=q.get("costo_admin_parcial", 0.0),
                tramo_base_origen_km=q.get("tramo_base_origen_km", 0.0),
                tramo_origen_destino_km=q.get("tramo_origen_destino_km", 0.0),
                tramo_destino_base_km=q.get("tramo_destino_base_km", 0.0),
                tramo_base_origen_min=q.get("tramo_base_origen_min", 0),
                tramo_origen_destino_min=q.get("tramo_origen_destino_min", 0),
                tramo_destino_base_min=q.get("tramo_destino_base_min", 0),
                extra_servicio_min=q.get("extra_servicio_min", 0),
                estado=q.get("estado", "sent"),
                confirmado_en=q.get("confirmado_en"),
                sent_at=q.get("sent_at"),
                cancelled_at=q.get("cancelled_at"),
                completed_at=q.get("completed_at"),
                voided_at=q.get("voided_at"),
                fecha_hora_preferida=q.get("fecha_hora_preferida"),
                notas_confirmacion=q.get("notas_confirmacion"),
                created_at=q.get("created_at") or datetime.now(timezone.utc)
            )
            session.add(quote)
            session.flush() # Para obtener el ID
            quote_map[str(q["_id"])] = quote.id
        session.commit()

        # --- RESERVAS (BOOKINGS) ---
        print("Migrando reservas...")
        mongo_bookings = list(mongo_db["bookings"].find())
        for b in mongo_bookings:
            m_qid = b.get("quote_id")
            s_qid = str(quote_map.get(m_qid)) if m_qid in quote_map else m_qid
            
            booking = dbBooking(
                date=b.get("date"),
                time=b.get("time"),
                quote_id=s_qid,
                status=b.get("status", "reserved"),
                confirmed_at=b.get("confirmed_at"),
                created_at=b.get("created_at") or datetime.now(timezone.utc)
            )
            session.add(booking)
        
        # --- CONFIGURACIÓN DE PRECIOS ---
        print("Migrando configuración de precios...")
        mongo_pcfg = mongo_db["config"].find_one({"_id": "pricing_vars"})
        if mongo_pcfg:
            data = {k: v for k, v in mongo_pcfg.items() if k != "_id"}
            pcfg = dbPricingConfig(
                id="pricing_vars",
                config_data=data,
                updated_at=datetime.now(timezone.utc)
            )
            session.merge(pcfg)
        
        session.commit()
    
    print("--- MIGRACIÓN COMPLETADA EXITOSAMENTE ---")

if __name__ == "__main__":
    migrate()
