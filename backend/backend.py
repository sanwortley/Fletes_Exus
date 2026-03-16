# backend/backend.py

# ===================================
# 🚛 FLETES JAVIER – BACKEND COMPLETO
# ===================================

from datetime import datetime, timezone, timedelta
from math import radians, sin, cos, asin, sqrt
import os
import calendar  # ✅ AÑADIDO (para mes/año)
from typing import Optional, Dict, Any, List

# SEGURIDAD
from .security.security_bootstrap import harden_app
from .security.auth_dep import require_api_key
from .security.rate_limit import install_rate_limit, limiter
from .security.security_auth import hash_password, verify_password, check_lock, register_fail, reset_fail

import requests
from fastapi import FastAPI, HTTPException, Depends, Body, BackgroundTasks, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from .database import engine, get_session, init_db
from .models.models import (
    dbUser, dbQuote, dbBooking, dbAvailabilityOverride, 
    dbBlockRule, dbGlobalConfig, dbPricingConfig
)
from dotenv import load_dotenv
load_dotenv(override=True)

# FRONTEND
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

# Notificaciones (tu módulo existente)
from .notifications import send_whatsapp_to_javier, send_email_to_admin

from urllib.parse import quote_plus



# =========================
# App & CORS
# =========================
app = FastAPI(title="Fletes Javier API")

harden_app(app)
install_rate_limit(app)


# =========================
# Frontend estático
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]   # .../Exus
FRONT_DIR = BASE_DIR / "frontend"

# SOLO assets con cache de 1 hora para fluidez
app.mount("/static", StaticFiles(directory=FRONT_DIR / "static"), name="static")
app.mount("/images", StaticFiles(directory=FRONT_DIR / "images"), name="images")

@app.get("/api/ping", include_in_schema=False)
def ping():
    return {"ok": True}


# ======= FRONTEND ROUTES =======

# Página principal
@app.get("/", include_in_schema=False)
def serve_home():
    return FileResponse(FRONT_DIR / "index.html")

# Redirigir /index → /
@app.get("/index", include_in_schema=False)
def redirect_index():
    return RedirectResponse(url="/", status_code=308)

@app.get("/index.html", include_in_schema=False)
def redirect_index_html():
    return RedirectResponse(url="/", status_code=308)

# Redirigir /presupuesto → /
@app.get("/presupuesto", include_in_schema=False)
def presupuesto_page():
    return FileResponse(FRONT_DIR / "presupuesto.html")

# Redirigir /admin → /
@app.get("/admin", include_in_schema=False)
@app.get("/admin/", include_in_schema=False)
def admin_page():
    return FileResponse(FRONT_DIR / "admin.html")




ALLOWED_ORIGINS = [o.strip() for o in (os.getenv("ALLOWED_ORIGINS") or "").split(",") if o.strip()]
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# =========================
# Database Initialization (SQL)
# =========================
@app.on_event("startup")
def on_startup():
    init_db()
    print("Database synchronized (SQL)")

# ✅ Colecciones (ahora son tablas, se manejan vía Session)
# quotes, users, availability, bookings, block_rules, block_config

DEFAULT_SLOTS = [
    "08:00", "09:00", "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00", "16:00", "17:00",
    "18:00", "19:00", "20:00", "21:00", "22:00"
]

# ✅ índices útiles
# Legacy MongoDB index creation removed

# Eliminated MongoDB startup check as we use SQL on_startup

# =========================
# Config de cálculo (.env)
# =========================
ROUTING_PROVIDER = (os.getenv("ROUTING_PROVIDER") or "google").lower()  # google | ors
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
MAPS_REGION = os.getenv("MAPS_REGION", "AR")
MAPS_LANGUAGE = os.getenv("MAPS_LANGUAGE", "es")
ORS_API_KEY = os.getenv("ORS_API_KEY")

BASE_DIRECCION = os.getenv("BASE_DIRECCION", "Córdoba, Argentina")
DEFAULT_LOCALITY = os.getenv("DEFAULT_LOCALITY", "Córdoba, Argentina")

# =========================
# Config de cálculo (Dynamic + .env fallback)
# =========================
from .config_manager import DynamicConfig

# Las variables globales se han eliminado para usar DynamicConfig.get_values(db) en tiempo de ejecución.
# Se mantienen solo las estáticas que no cambian (API Keys, etc).


# Contacto del profesional
PRO_PHONE = os.getenv("PRO_PHONE", "+5493516678989")
PRO_NAME = os.getenv("PRO_NAME", "Fletes Javier")

# =========================
# Modelos
# =========================
class QuoteIn(BaseModel):
    nombre_cliente: str = Field(None, alias="nombre")
    telefono: str
    tipo_carga: str
    origen: str
    destino: str
    fecha: Optional[str] = None
    ayudante: bool = False
    regreso_base: Optional[bool] = None
    hora_inicio: Optional[str] = None
    hora_fin: Optional[str] = None
    horas_reales: Optional[float] = None
    peajes: int = 0
    viaticos: float = 0.0
    accepted_terms: bool = False
    accepted_terms_at: Optional[datetime] = None
    model_config = {"populate_by_name": True, "extra": "allow"}

    # ✅ AÑADIDO: turno elegido por el usuario
    fecha_turno: Optional[str] = None   # YYYY-MM-DD
    hora_turno: Optional[str] = None    # HH:MM


class ConfirmPayload(BaseModel):
    fecha_hora_preferida: Optional[str] = None
    notas: Optional[str] = None

class LoginIn(BaseModel):
    username: str | None = Field(None, alias="email")
    password: str
    model_config = {"populate_by_name": True}

class LoginOut(BaseModel):
    ok: bool
    message: str | None = None
    token: str | None = None
    role: str = "admin"

class AvailabilityDayIn(BaseModel):
    date: str                # YYYY-MM-DD
    enabled: bool = True
    slots: List[str] = []

class BlockRuleIn(BaseModel):
    """Regla de bloqueo persistente almacenada en block_rules."""
    hour_from: str
    hour_to: str
    apply_all: bool = False
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    label: Optional[str] = None      # descripción opcional

class ChangeCredsIn(BaseModel):
    new_username: str
    new_password: str

# (lo dejamos por compat si después lo querés usar)
class ReserveIn(BaseModel):
    date: str  # YYYY-MM-DD
    slot: str  # "09:30"
    quote_id: Optional[str] = None


# =========================
# Helpers
# =========================
def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(min(1, sqrt(a)))
    return R * c

def _parse_hora(h: str) -> datetime:
    h = h.strip()
    try:
        if len(h) <= 5 and ":" in h:
            today = datetime.now()
            hh, mm = map(int, h.split(":"))
            return today.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return datetime.fromisoformat(h.replace(" ", "T"))
    except Exception:
        return datetime.now()

def _normalize_addr(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return DEFAULT_LOCALITY
    if DEFAULT_LOCALITY.lower() not in s.lower():
        return f"{s}, {DEFAULT_LOCALITY}"
    return s

def _geocode_google(address: str) -> Optional[Dict[str, float]]:
    if not GOOGLE_MAPS_API_KEY:
        return None
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address, "key": GOOGLE_MAPS_API_KEY, "language": MAPS_LANGUAGE, "region": MAPS_REGION}
        js = requests.get(url, params=params, timeout=12).json()
        if js.get("status") != "OK":
            return None
        loc = js["results"][0]["geometry"]["location"]
        return {"lat": loc["lat"], "lng": loc["lng"]}
    except Exception:
        return None

def _distance_time_google(origen: str, destino: str) -> Optional[Dict[str, Any]]:
    if not GOOGLE_MAPS_API_KEY:
        return None
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": origen, "destinations": destino, "key": GOOGLE_MAPS_API_KEY,
            "language": MAPS_LANGUAGE, "region": MAPS_REGION
        }
        js = requests.get(url, params=params, timeout=12).json()
        if js.get("status") != "OK":
            return None
        rows = js.get("rows", [])
        if not rows or not rows[0].get("elements"):
            return None
        el = rows[0]["elements"][0]
        if el.get("status") != "OK":
            return None
        dist_m = el["distance"]["value"]
        dur_s = el["duration"]["value"]
        return {"dist_km": dist_m/1000.0, "tiempo_viaje_min": int(round(dur_s/60))}
    except Exception:
        return None

def _distance_time_ors(origen: str, destino: str) -> Optional[Dict[str, Any]]:
    if not ORS_API_KEY:
        return None
    try:
        g_url = "https://api.openrouteservice.org/geocode/search"
        hdr = {"Authorization": ORS_API_KEY}
        g1 = requests.get(g_url, headers=hdr, params={"text": origen, "size": 1}, timeout=12).json()
        g2 = requests.get(g_url, headers=hdr, params={"text": destino, "size": 1}, timeout=12).json()

        def pick(g):
            feats = g.get("features") or []
            if not feats:
                return None
            lon, lat = feats[0]["geometry"]["coordinates"]
            return lat, lon

        o = pick(g1); d = pick(g2)
        if not o or not d:
            return None

        r_url = "https://api.openrouteservice.org/v2/directions/driving-car"
        js = requests.get(
            r_url, headers=hdr,
            params={"start": f"{o[1]},{o[0]}", "end": f"{d[1]},{d[0]}"},
            timeout=12
        ).json()
        feat = (js.get("features") or [None])[0]
        if not feat:
            return None
        s = feat["properties"]["summary"]
        return {"dist_km": s["distance"]/1000.0, "tiempo_viaje_min": int(round(s["duration"]/60))}
    except Exception:
        return None

def _distance_time_fallback(session: Session, origen: str, destino: str) -> Dict[str, Any]:
    # Obtener config actual
    conf = DynamicConfig.get_values(session)
    FACTOR_TRAZADO = conf["FACTOR_TRAZADO"]
    VEL_KMH = conf["VEL_KMH"]

    o = _geocode_google(origen) if GOOGLE_MAPS_API_KEY else None
    d = _geocode_google(destino) if GOOGLE_MAPS_API_KEY else None
    if o and d:
        dist_km = _haversine_km(o["lat"], o["lng"], d["lat"], d["lng"]) * FACTOR_TRAZADO
    else:
        dist_km = 10.0
    tiempo_viaje_min = int(round((dist_km / max(VEL_KMH, 1)) * 60))
    return {"dist_km": round(dist_km, 2), "tiempo_viaje_min": int(tiempo_viaje_min)}

AR_TZ = timezone(timedelta(hours=-3))

def _today_ar_str() -> str:
    return datetime.now(AR_TZ).date().isoformat()

def _get_blocked_slots_for_date(session: Session, date_str: str) -> set:
    """
    Devuelve el conjunto de horarios bloqueados por las reglas activas para una fecha dada.
    Si blocks_enabled es False, devuelve set vacío (sin bloqueos).
    """
    statement_cfg = select(dbGlobalConfig).where(dbGlobalConfig.id == "global_config")
    cfg = session.exec(statement_cfg).first()
    
    if cfg and not cfg.blocks_enabled:
        return set()

    today_str = _today_ar_str()
    blocked = set()
    
    statement_rules = select(dbBlockRule)
    rules = session.exec(statement_rules).all()
    
    for rule in rules:
        hf  = rule.hour_from
        ht  = rule.hour_to
        if not hf or not ht:
            continue
        if rule.apply_all:
            # Aplica a todos los días desde hoy
            if date_str < today_str:
                continue
        else:
            df = rule.date_from
            dt = rule.date_to
            if not df or not dt or not (df <= date_str <= dt):
                continue
        for slot in DEFAULT_SLOTS:
            if hf <= slot <= ht:
                blocked.add(slot)
    return blocked

def _purge_expired_unconfirmed(session: Session):
    hoy = _today_ar_str()

    statement = select(dbQuote).where(
        dbQuote.estado.in_(["sent", "rechazado"]),
        dbQuote.fecha_turno < hoy
    )
    expired = session.exec(statement).all()

    if not expired:
        return 0

    count = len(expired)
    for q in expired:
        session.delete(q)
    session.commit()
    return count



def _marcar_realizados(session: Session):
    hoy = _today_ar_str()

    # Confirmado + fecha_turno pasada => Realizado
    statement = select(dbQuote).where(
        dbQuote.estado == "confirmado",
        dbQuote.fecha_turno < hoy
    )
    quotes_to_update = session.exec(statement).all()
    
    for q in quotes_to_update:
        q.estado = "realizado"
        # Nota: en SQLModel no tenemos realizado_en en el modelo dbQuote, 
        # pero podemos agregarlo o ignorarlo por ahora si no es crítico.
        # Mantendremos la consistencia con el modelo definido.
        # q.realizado_en = datetime.now(timezone.utc)
    
    if quotes_to_update:
        session.commit()


def calcular_ruta(session: Session, origen: str, destino: str) -> Dict[str, Any]:
    used = None
    res = None
    if ROUTING_PROVIDER == "google":
        res = _distance_time_google(origen, destino); used = "google"
        if not res and ORS_API_KEY:
            res = _distance_time_ors(origen, destino); used = "ors(fallback)"
    else:
        res = _distance_time_ors(origen, destino); used = "ors"
        if not res and GOOGLE_MAPS_API_KEY:
            res = _distance_time_google(origen, destino); used = "google(fallback)"
    if not res:
        res = _distance_time_fallback(session, origen, destino); used = "fallback(heuristica_10km)"
    print(f"[route] provider_used={used} origen='{origen}' destino='{destino}' -> {res}")
    return res

# =========================
# Cálculo de costos
# =========================
# =========================
# Cálculo de costos
# =========================
def calcular_costos(
    session: Session, # Añadimos session
    dist_km: float,
    tiempo_viaje_min: int,
    ayudante: bool,
    horas_reales: Optional[float] = None,
    peajes: int = 0,
    viaticos: float = 0.0,
    extra_servicio_min: int = 0,
) -> Dict[str, float]:

    # 1) Obtener configuración dinámica
    conf = DynamicConfig.get_values(session)
    
    FACTOR_PONDERACION = conf.get("FACTOR_PONDERACION", 1.5)
    COSTO_HORA = conf.get("COSTO_HORA", 0.0)
    COSTO_HORA_AYUDANTE = conf.get("COSTO_HORA_AYUDANTE", 0.0)
    COSTO_CHOFER_HORA = conf.get("COSTO_CHOFER_HORA", 0.0)
    COSTO_ADMIN_HORA = conf.get("COSTO_ADMIN_HORA", 0.0)
    KM_POR_LITRO = max(conf.get("KM_POR_LITRO", 8.0), 0.1)
    COSTO_LITRO = conf.get("COSTO_LITRO", 0.0)
    MANTENIMIENTO_PCT = conf.get("MANTENIMIENTO_PCT", 0.0)
    COSTO_PEAJE = conf.get("COSTO_PEAJE", 0.0)
    CARGA_DESC_H = conf.get("CARGA_DESC_H", 0.0)
    BASE_FIJA = conf.get("BASE_FIJA", 0.0)
    MIN_TOTAL = conf.get("MIN_TOTAL", 0.0)
    REDONDEO_MIN = conf.get("REDONDEO_MIN", 0)
    
    # Flags de comportamiento
    INCLUIR_CHOFER_ADMIN = conf.get("INCLUIR_CHOFER_ADMIN_EN_TOTAL", False)

    # 2) Tiempo de viaje base (manejo)
    # Si el tiempo es 0 o muy bajo, puede haber un error de API o velocidad 0
    horas_manejo = (horas_reales if (horas_reales and horas_reales > 0) else (tiempo_viaje_min / 60.0))
    if horas_manejo < 0.01 and dist_km > 0:
        # Fallback de velocidad si algo falló (35km/h)
        horas_manejo = dist_km / 35.0

    # 3) Tiempo Total (Según Excel: (Manejo_Total * Ponderación) + Carga/Descarga)
    # Ya no sumamos extra_servicio_min por fuera para evitar duplicación
    tiempo_total_h = (horas_manejo * FACTOR_PONDERACION) + CARGA_DESC_H

    # 4) Redondeo opcional
    if REDONDEO_MIN > 0:
        import math
        bloque_h = REDONDEO_MIN / 60.0
        tiempo_total_h = bloque_h * math.ceil(tiempo_total_h / bloque_h)

    # 5) Cálculos de costos basados en TIEMPO
    costo_tiempo_base = tiempo_total_h * COSTO_HORA
    
    # Mantenimiento como % del costo de tiempo (Javier Excel: 20%)
    pct_dec = MANTENIMIENTO_PCT / 100.0 if MANTENIMIENTO_PCT >= 1 else MANTENIMIENTO_PCT
    mantenimiento = costo_tiempo_base * pct_dec
    
    # Ayudante (solo si el cliente lo pide)
    costo_ayudante = (tiempo_total_h * COSTO_HORA_AYUDANTE) if ayudante else 0.0
    
    # Costos parciales internos (informativos)
    costo_chofer = tiempo_total_h * COSTO_CHOFER_HORA
    costo_admin = tiempo_total_h * COSTO_ADMIN_HORA

    # 6) Cálculos de costos basados en DISTANCIA
    costo_combustible = (dist_km / KM_POR_LITRO) * COSTO_LITRO
    costo_peajes = peajes * COSTO_PEAJE
    
    costo_distancia_total = costo_combustible + costo_peajes + viaticos

    # 7) MONTO TOTAL ESTIMADO
    # Suma exacta de Javier: Costo Tiempo + Mantenimiento + Ayudante + Costo Distancia
    monto_estimado = (
        BASE_FIJA
        + costo_tiempo_base
        + mantenimiento
        + costo_ayudante
        + costo_distancia_total
    )
    
    # Si el admin activó incluir costos internos en el precio al cliente
    if INCLUIR_CHOFER_ADMIN:
        monto_estimado += (costo_chofer + costo_admin)

    monto_estimado = max(monto_estimado, MIN_TOTAL)

    return {
        "horas_base": round(tiempo_total_h, 2),
        "tiempo_servicio_min": int(round(tiempo_total_h * 60)),
        "costo_tiempo_base": round(costo_tiempo_base, 2),
        "mantenimiento": round(mantenimiento, 2),
        "costo_tiempo": round(costo_tiempo_base + mantenimiento + costo_ayudante, 2),
        "costo_combustible": round(costo_combustible, 2),
        "peajes_total": round(costo_peajes, 2),
        "viaticos": round(viaticos, 2),
        "costo_ayudante": round(costo_ayudante, 2),
        "costo_chofer_parcial": round(costo_chofer, 2),
        "costo_admin_parcial": round(costo_admin, 2),
        "monto_estimado": round(monto_estimado, 2),
    }

# =========================
# Serializaciones
# =========================
def _quote_public(doc: dbQuote) -> dict:
    return {
        "id": doc.id,
        "nombre_cliente": doc.nombre_cliente,
        "telefono": doc.telefono,
        "tipo_carga": doc.tipo_carga,
        "origen": doc.origen,
        "destino": doc.destino,
        "fecha": doc.fecha,
        "ayudante": bool(doc.ayudante),
        "regreso_base": bool(doc.regreso_base),
        "dist_km": float(doc.dist_km),
        "tiempo_viaje_min": int(doc.tiempo_viaje_min),
        "tiempo_servicio_min": int(doc.tiempo_servicio_min),
        "costo_tiempo": float(doc.costo_tiempo),
        "costo_combustible": float(doc.costo_combustible),
        "monto_estimado": float(doc.monto_estimado),
        "estado": doc.estado,

        # ✅ AÑADIDO: exponer turno (para que lo muestres en UI/admin)
        "fecha_turno": doc.fecha_turno,
        "hora_turno": doc.hora_turno,
    }

def _contact_urls(quote_id: str) -> dict:
    msg = f"Hola {PRO_NAME}, te envié un presupuesto desde la web. ID: {quote_id}."
    wa = f"https://wa.me/{PRO_PHONE.replace('+','').replace(' ','')}?text={quote_plus(msg)}"
    tel = f"tel:{PRO_PHONE}"
    return {"whatsapp": wa, "tel": tel}

# =========================
# Notificación (background)
# =========================
def _notify_new_quote(doc: dict):
    wa_res = None
    email_res = None
    try:
        # 1) WhatsApp
        text_wa = format_whatsapp_quote(doc)
        wa_res = send_whatsapp_to_javier(text_wa)
        
        # 2) Email
        subject = f"Nuevo Presupuesto - {doc.get('nombre_cliente', 'Cliente')}"
        body_text = format_whatsapp_quote(doc) # Reusamos texto plano para el email plain
        body_html = format_email_quote_html(doc)
        email_res = send_email_to_admin(subject, body_text, body_html)
        
    except Exception as e:
        print(f"[_notify_new_quote] Error: {e}")
        if wa_res is None: wa_res = {"ok": "false", "error": str(e)}
        if email_res is None: email_res = {"ok": "false", "error": str(e)}
        
    return {"whatsapp": wa_res, "email": email_res}

def _yn(v):
    return "Sí" if bool(v) else "No"

def _money(n):
    try:
        return f"${float(n):,.0f}".replace(",", ".")
    except Exception:
        return f"${n}"

# ==== NUEVO: helpers de Maps robustos ====
def _ensure_locality(addr: str, locality: str = DEFAULT_LOCALITY) -> str:
    s = (addr or "").strip()
    if not s:
        return locality
    if locality and locality.lower() not in s.lower():
        return f"{s}, {locality}"
    return s

def maps_link(addr: str = "", lat: float | None = None, lng: float | None = None) -> str:
    """
    - Si hay coords: usa lat,lng (evita ambigüedades).
    - Si no: fuerza localidad y hace URL-encode del texto.
    """
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps/search/?api=1&query={lat:.6f}%2C{lng:.6f}"
    q = quote_plus(_ensure_locality(addr))
    return f"https://www.google.com/maps/search/?api=1&query={q}"

def format_whatsapp_quote(doc: dict) -> str:
    nombre  = doc.get("nombre_cliente", "-")
    tel     = doc.get("telefono", "-")
    tipo    = doc.get("tipo_carga", "-")
    fecha   = doc.get("fecha", "-")
    ayud    = _yn(doc.get("ayudante"))
    origen  = doc.get("origen", "-")
    destino = doc.get("destino", "-")
    _id     = str(doc.get("_id") or doc.get("id") or "-")

    # ✅ turno
    ft = doc.get("fecha_turno")
    ht = doc.get("hora_turno")
    turno_line = f"• Turno: *{ft} {ht}*\n" if ft and ht else ""

    o_lat = doc.get("origen_lat");  o_lng = doc.get("origen_lng")
    d_lat = doc.get("destino_lat"); d_lng = doc.get("destino_lng")
    link_origen  = maps_link(origen,  o_lat, o_lng)
    link_destino = maps_link(destino, d_lat, d_lng)

    dist_km   = doc.get("dist_km", 0) or 0
    t_manejo  = doc.get("tiempo_viaje_min", 0) or 0
    t_srv     = doc.get("tiempo_servicio_min", 0) or 0

    costo_t   = doc.get("costo_tiempo", 0) or 0
    costo_c   = doc.get("costo_combustible", 0) or 0
    costo_a   = doc.get("costo_ayudante", 0) or 0
    total     = doc.get("monto_estimado", 0) or 0

    b_o_km  = doc.get("tramo_base_origen_km", 0) or 0
    b_o_min = doc.get("tramo_base_origen_min", 0) or 0
    o_d_km  = doc.get("tramo_origen_destino_km", 0) or 0
    o_d_min = doc.get("tramo_origen_destino_min", 0) or 0

    return (
        "🧾 *Nuevo presupuesto enviado desde la web*\n"
        f"• Cliente: *{nombre}*  ({tel})\n"
        f"• Tipo: *{tipo}*   • Fecha: *{fecha}*\n"
        + turno_line +
        f"• Ayudante: *{ayud}*   • *Incluye regreso a base*\n"
        f"• Origen: {origen}\n"
        f"  ↳ {link_origen}\n"
        f"• Destino: {destino}\n"
        f"  ↳ {link_destino}\n"
        "—\n"
        f"• Distancia total: *{dist_km:.2f} km*   • Manejo: *{t_manejo} min*\n"
        f"• Servicio (total): *{t_srv} min*\n"
        f"• Total estimado: *{_money(total)}*\n"
        f"  - Tiempo: {_money(costo_t)}  - Combustible: {_money(costo_c)}  - Ayudante: {_money(costo_a)}\n"
        "• Detalle tramos:\n"
        f"  · Base→Origen: {b_o_km:.2f} km / {b_o_min} min\n"
        f"  · Origen→Destino: {o_d_km:.2f} km / {o_d_min} min\n"
        "—\n"
        f"ID: `{_id}`"
    )

def format_email_quote_html(doc: dict) -> str:
    nombre  = doc.get("nombre_cliente", "-")
    tel     = doc.get("telefono", "-")
    tipo    = doc.get("tipo_carga", "-")
    fecha   = doc.get("fecha", "-")
    ayud    = _yn(doc.get("ayudante"))
    origen  = doc.get("origen", "-")
    destino = doc.get("destino", "-")
    _id     = str(doc.get("_id") or doc.get("id") or "-")
    
    ft = doc.get("fecha_turno")
    ht = doc.get("hora_turno")
    turno_html = f"<li><strong>Turno reservado:</strong> {ft} {ht}</li>" if ft and ht else ""

    total = doc.get("monto_estimado", 0) or 0
    dist_km = doc.get("dist_km", 0) or 0
    
    admin_url = os.getenv("ADMIN_URL", "https://alquilerfletes.com.ar/admin")
    
    # Construir URL de ruta completa: Base -> Origen -> Destino -> Base
    base_addr = os.getenv("BASE_DIRECCION", "Córdoba, Argentina")
    route_url = f"https://www.google.com/maps/dir/?api=1&origin={quote_plus(base_addr)}&destination={quote_plus(base_addr)}&waypoints={quote_plus(origen)}|{quote_plus(destino)}"

    # Generar imagen estática del Mapa
    # Marcadores: B (Base), 1 (Origen), 2 (Destino)
    static_map_url = (
        f"https://maps.googleapis.com/maps/api/staticmap?"
        f"size=600x300&scale=2&maptype=roadmap"
        f"&markers=color:red|label:B|{quote_plus(base_addr)}"
        f"&markers=color:blue|label:1|{quote_plus(origen)}"
        f"&markers=color:green|label:2|{quote_plus(destino)}"
        f"&key={GOOGLE_MAPS_API_KEY}"
    )

    return f"""
    <div style="font-family: sans-serif; max-width: 600px; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
        <h2 style="color: #D3A129;">NUEVO PRESUPUESTO RECIBIDO</h2>
        <p>Se ha generado una nueva solicitud desde la web:</p>
        <ul style="list-style: none; padding: 0;">
            <li><strong>Cliente:</strong> {nombre}</li>
            <li><strong>Teléfono:</strong> {tel}</li>
            <li><strong>Tipo de Carga:</strong> {tipo}</li>
            <li><strong>Fecha sugerida:</strong> {fecha}</li>
            {turno_html}
            <li><strong>Origen:</strong> {origen}</li>
            <li><strong>Destino:</strong> {destino}</li>
            <li><strong>Distancia:</strong> {dist_km:.2f} km</li>
            <li><strong>Ayudante:</strong> {ayud}</li>
        </ul>

        <!-- Vista previa del mapa -->
        <div style="margin-top: 20px; border-radius: 8px; overflow: hidden; border: 1px solid #ddd;">
            <a href="{route_url}" target="_blank">
                <img src="{static_map_url}" alt="Mapa de Ruta" style="width: 100%; height: auto; display: block;">
            </a>
        </div>

        <div style="background: #f9f9f9; padding: 15px; border-radius: 5px; margin-top: 20px;">
            <p style="margin: 0; font-size: 1.2rem;">Total Estimado: <strong>{_money(total)}</strong></p>
        </div>
        <p style="margin-top: 25px; margin-bottom: 10px;">
            <a href="{admin_url}" 
               style="background: #2F4858; color: white; padding: 12px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; margin-right: 8px; margin-bottom: 8px; font-size: 14px;">
               PANEL
            </a>
            <a href="https://wa.me/549{(''.join(c for c in str(tel) if c.isdigit()))[-10:]}" 
               style="background: #25D366; color: white; padding: 12px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; margin-right: 8px; margin-bottom: 8px; font-size: 14px;">
               WHATSAPP
            </a>
            <a href="{route_url}" 
               style="background: #4285F4; color: white; padding: 12px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; margin-bottom: 8px; font-size: 14px;">
               VER RUTA
            </a>
        </p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
        <small style="color: #999;">ID de referencia: {_id}</small>
    </div>
    """

def format_whatsapp_confirmed(doc: dict) -> str:
    nombre = doc.get("nombre_cliente", "-")
    tel = doc.get("telefono", "-")
    _id = str(doc.get("_id") or doc.get("id") or "-")

    # Turno (si existe)
    ft = doc.get("fecha_turno") or doc.get("fecha") or "-"
    ht = doc.get("hora_turno") or ""

    # Link para hablarle al cliente por WhatsApp (AR). Limpia todo a dígitos.
    tel_digits = "".join([c for c in str(tel) if c.isdigit()])
    wa_cliente = f"https://wa.me/54{tel_digits}" if tel_digits else ""

    return (
        "✅ *Presupuesto confirmado*\n"
        f"• Cliente: *{nombre}*\n"
        f"• Tel: *{tel}*\n"
        + (f"• WhatsApp cliente: {wa_cliente}\n" if wa_cliente else "")
        + f"• Turno: *{ft}{(' ' + ht) if ht else ''}*\n"
        "—\n"
        f"ID: `{_id}`"
    )


def _notify_confirmed_quote(doc: dict):
    wa_res = None
    try:
        text = format_whatsapp_confirmed(doc)
        wa_res = send_whatsapp_to_javier(text)
    except Exception as e:
        wa_res = {"ok": "false", "error": str(e)}
    return {"whatsapp": wa_res}




# =========================
# ✅ AGENDA (Disponibilidad)
# =========================

@app.get("/api/availability")
def get_availability(
    month: str = Query(..., description="YYYY-MM"),
    session: Session = Depends(get_session)
):
    """
    Público: devuelve disponibilidad real (Merge de DEFAULT_SLOTS + Disponibilidad Admin + Bookings)
    { days: { 'YYYY-MM-DD': ['08:00', '09:00', ...] } }
    """
    try:
        year, mon = map(int, month.split("-"))
        last_day = calendar.monthrange(year, mon)[1]
    except Exception:
        raise HTTPException(status_code=400, detail="month inválido. Usar YYYY-MM")

    start = f"{year:04d}-{mon:02d}-01"
    end   = f"{year:04d}-{mon:02d}-{last_day:02d}"

    # 1) Obtener overrides del admin
    statement_ovr = select(dbAvailabilityOverride).where(
        dbAvailabilityOverride.date >= start,
        dbAvailabilityOverride.date <= end
    )
    overrides = {ovr.date: ovr for ovr in session.exec(statement_ovr).all()}
    
    # 2) Obtener bookings (reservados o confirmados)
    statement_booked = select(dbBooking).where(
        dbBooking.date >= start,
        dbBooking.date <= end,
        dbBooking.status.in_(["reserved", "confirmed"])
    )
    booked = {}
    for b in session.exec(statement_booked).all():
        booked.setdefault(b.date, set()).add(b.time)

    # 3) Obtener configuración global de bloqueos y REGLAS
    statement_cfg = select(dbGlobalConfig).where(dbGlobalConfig.id == "global_config")
    cfg = session.exec(statement_cfg).first()
    is_blocking_active = cfg.blocks_enabled if cfg else True
    
    rules_cache = []
    if is_blocking_active:
        statement_rules = select(dbBlockRule)
        rules_cache = session.exec(statement_rules).all()

    today_str = _today_ar_str()
    days: Dict[str, List[str]] = {}
    
    # 4) Construir respuesta iterando días del mes
    for d in range(1, last_day + 1):
        date_str = f"{year:04d}-{mon:02d}-{d:02d}"
        
        # Base: lo que el admin configuró o el default
        day_ovr = overrides.get(date_str)
        if day_ovr and not day_ovr.enabled:
            days[date_str] = []
            continue
            
        base_slots = day_ovr.slots if (day_ovr and day_ovr.slots) else DEFAULT_SLOTS
        
        # Restar bookings
        day_booked = booked.get(date_str, set())
        final_slots = [s for s in base_slots if s not in day_booked]

        # Aplicar reglas dinámicas de bloqueo desde el cache (OPTIMIZADO)
        if is_blocking_active and rules_cache:
            blocked_by_rules = set()
            for rule in rules_cache:
                hf = rule.hour_from
                ht = rule.hour_to
                if not hf or not ht: continue

                # Validar si aplica según modo (apply_all o rango)
                if rule.apply_all:
                    if date_str < today_str: continue
                else:
                    df = rule.date_from
                    dt = rule.date_to
                    if not df or not dt or not (df <= date_str <= dt): continue
                
                # Agregar slots al set de bloqueados
                for slot in DEFAULT_SLOTS:
                    if hf <= slot <= ht:
                        blocked_by_rules.add(slot)
            
            if blocked_by_rules:
                final_slots = [s for s in final_slots if s not in blocked_by_rules]

        # Si el resultado es distinto al DEFAULT_SLOTS original, lo enviamos
        if sorted(final_slots) != sorted(DEFAULT_SLOTS):
            days[date_str] = final_slots

    return {"ok": True, "month": month, "days": days}

@app.get("/api/admin/availability")
def admin_get_availability(
    month: str = Query(..., description="YYYY-MM"),
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Admin: devuelve TODO (enabled true/false + slots) para pintar grises
    """
    try:
        year, mon = map(int, month.split("-"))
        last_day = calendar.monthrange(year, mon)[1]
    except Exception:
        raise HTTPException(status_code=400, detail="month inválido. Usar YYYY-MM")

    start = f"{year:04d}-{mon:02d}-01"
    end   = f"{year:04d}-{mon:02d}-{last_day:02d}"

    statement = select(dbAvailabilityOverride).where(
        dbAvailabilityOverride.date >= start,
        dbAvailabilityOverride.date <= end
    )
    items = session.exec(statement).all()
    
    # Serializamos manualmente los items para el frontend si es necesario, 
    # o confiamos en que SQLModel se porta bien (JSON field necesita cuidado)
    return {"ok": True, "month": month, "items": items}

@app.post("/api/availability/day")
def upsert_availability_day(
    body: AvailabilityDayIn,
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):

    if not body.date or not isinstance(body.slots, list):
        raise HTTPException(status_code=400, detail="Se requiere 'date' y 'slots' (lista)")

    # 🔒 1) Buscar horarios ya reservados o confirmados
    statement_booked = select(dbBooking).where(
        dbBooking.date == body.date,
        dbBooking.status.in_(["reserved", "confirmed"])
    )
    ocupados = set(b.time for b in session.exec(statement_booked).all())

    # 🔒 2) Filtrar slots enviados por el admin
    slots_validos = [s for s in body.slots if s not in ocupados]

    statement_ovr = select(dbAvailabilityOverride).where(
        dbAvailabilityOverride.date == body.date
    )
    ovr = session.exec(statement_ovr).first()
    
    if ovr:
        ovr.enabled = bool(body.enabled)
        ovr.slots = slots_validos
        ovr.updated_at = datetime.now(timezone.utc)
    else:
        ovr = dbAvailabilityOverride(
            date=body.date,
            enabled=bool(body.enabled),
            slots=slots_validos
        )
        session.add(ovr)
    
    session.commit()

    return {
        "ok": True,
        "bloqueados": list(ocupados),
        "slots_guardados": slots_validos
    }

@app.delete("/api/availability/all")
def delete_all_availability(
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Borra ABSOLUTAMENTE TODOS los overrides manuales de disponibilidad.
    """
    statement = select(dbAvailabilityOverride)
    items = session.exec(statement).all()
    for item in items:
        session.delete(item)
    session.commit()
    return {"ok": True, "message": "Toda la disponibilidad manual ha sido reseteada"}

@app.delete("/api/availability/day/{date_str}")
def delete_availability_day(
    date_str: str,
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Elimina cualquier override manual para un día, volviendo a DEFAULT_SLOTS.
    """
    if len(date_str) != 10:
        raise HTTPException(400, "Formato YYYY-MM-DD requerido")
    
    statement = select(dbAvailabilityOverride).where(dbAvailabilityOverride.date == date_str)
    item = session.exec(statement).first()
    if item:
        session.delete(item)
        session.commit()
    
    return {"ok": True}


@app.get("/api/admin/bookings/day")
def admin_get_bookings_day(
    date: str = Query(..., description="YYYY-MM-DD"),
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Devuelve horarios ocupados (reserved/confirmed) para bloquearlos en el panel de disponibilidad.
    """
    if not date or len(date) != 10:
        raise HTTPException(status_code=400, detail="date inválida. Usar YYYY-MM-DD")

    statement = select(dbBooking).where(
        dbBooking.date == date,
        dbBooking.status.in_(["reserved", "confirmed"])
    )
    ocupados = sorted(list(set(b.time for b in session.exec(statement).all() if b.time)))

    return {"ok": True, "date": date, "ocupados": ocupados}


# =========================
# ✅ Reglas de bloqueo horario (Admin)
# =========================

@app.get("/api/admin/block-rules")
def get_block_rules(
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Devuelve la lista de reglas de bloqueo y el estado global (blocks_enabled).
    """
    statement_cfg = select(dbGlobalConfig).where(dbGlobalConfig.id == "global_config")
    cfg = session.exec(statement_cfg).first()
    
    statement_rules = select(dbBlockRule)
    db_rules = session.exec(statement_rules).all()
    
    rules = []
    for r in db_rules:
        rules.append({
            "id":        str(r.id),
            "hour_from": r.hour_from,
            "hour_to":   r.hour_to,
            "apply_all": r.apply_all,
            "date_from": r.date_from,
            "date_to":   r.date_to,
            "label":     r.label,
        })
    return {
        "ok": True,
        "blocks_enabled": cfg.blocks_enabled if cfg else True,
        "rules": rules,
    }

@app.post("/api/admin/block-rules")
def add_block_rule(
    body: BlockRuleIn,
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Agrega una nueva regla de bloqueo persistente.
    """
    import re
    hh_re = re.compile(r"^\d{2}:\d{2}$")
    if not hh_re.match(body.hour_from) or not hh_re.match(body.hour_to):
        raise HTTPException(400, "hour_from y hour_to deben tener formato HH:MM")
    if body.hour_from > body.hour_to:
        raise HTTPException(400, "hour_from debe ser <= hour_to")
    if not body.apply_all and (not body.date_from or not body.date_to):
        raise HTTPException(400, "Especificá date_from y date_to, o activá apply_all")

    slots_affected = [h for h in DEFAULT_SLOTS if body.hour_from <= h <= body.hour_to]
    
    rule = dbBlockRule(
        hour_from=body.hour_from,
        hour_to=body.hour_to,
        apply_all=body.apply_all,
        date_from=body.date_from,
        date_to=body.date_to,
        label=body.label
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    
    return {"ok": True, "id": str(rule.id), "slots_affected": slots_affected}

@app.delete("/api/admin/block-rules/{rule_id}")
def delete_block_rule(
    rule_id: str,
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Elimina una regla de bloqueo por ID.
    """
    try:
        rid = int(rule_id)
    except Exception:
        raise HTTPException(400, "ID inválido")
    
    rule = session.get(dbBlockRule, rid)
    if not rule:
        raise HTTPException(404, "Regla no encontrada")
    
    session.delete(rule)
    session.commit()
    return {"ok": True}

@app.post("/api/admin/block-rules/toggle")
def toggle_block_rules(
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Alterna el estado global de los bloqueos (activo/inactivo).
    """
    statement = select(dbGlobalConfig).where(dbGlobalConfig.id == "global_config")
    cfg = session.exec(statement).first()
    
    new_val = not (cfg.blocks_enabled if cfg else True)
    
    if cfg:
        cfg.blocks_enabled = new_val
        cfg.updated_at = datetime.now(timezone.utc)
    else:
        cfg = dbGlobalConfig(id="global_config", blocks_enabled=new_val)
        session.add(cfg)
        
    session.commit()
    return {"ok": True, "blocks_enabled": new_val}


@app.get("/api/config")
def get_config():
    return {
        "google_maps_api_key": GOOGLE_MAPS_API_KEY,
        "default_locality": DEFAULT_LOCALITY,
        "maps_region": MAPS_REGION,
        "maps_language": MAPS_LANGUAGE
    }

# ✅ NUEVO: Endpoints de variables de presupuesto (Admin)
@app.get("/api/admin/config-vars")
def get_admin_config_vars(
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    return DynamicConfig.get_values(session)

@app.post("/api/admin/config-vars")
def update_admin_config_vars(
    payload: dict = Body(...),
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    try:
        updated = DynamicConfig.update_values(session, payload)
        return {"ok": True, "config": updated}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/admin/change-creds")
def change_admin_creds(
    body: ChangeCredsIn,
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    """
    Actualiza el usuario y contraseña del administrador.
    Busca por rol 'admin'.
    """
    new_user = body.new_username.strip().lower()
    new_pass = body.new_password.strip()

    if not new_user or not new_pass:
        raise HTTPException(status_code=400, detail="Usuario y contraseña no pueden estar vacíos")

    hashed = hash_password(new_pass)

    statement = select(dbUser).where(dbUser.role == "admin")
    admin = session.exec(statement).first()
    
    if admin:
        admin.email = new_user
        admin.username = new_user
        admin.password_hash = hashed
        admin.updated_at = datetime.now(timezone.utc)
    else:
        admin = dbUser(
            username=new_user,
            email=new_user,
            password_hash=hashed,
            role="admin"
        )
        session.add(admin)
    
    session.commit()
    return {"ok": True, "message": "Credenciales actualizadas exitosamente."}

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Fletes Javier API"}

def _calcular_desde_body(session: Session, body: QuoteIn) -> dict:
    # Normalizar
    nombre = body.nombre_cliente or body.__dict__.get("nombre_cliente")
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta nombre_cliente")

    origen_norm = _normalize_addr(body.origen)
    destino_norm = _normalize_addr(body.destino)
    base_norm = _normalize_addr(BASE_DIRECCION)

    # Tramos
    t1 = calcular_ruta(session, base_norm, origen_norm)
    t2 = calcular_ruta(session, origen_norm, destino_norm)

    dist_total = float(t1["dist_km"] + t2["dist_km"])
    tiempo_total_min = int(t1["tiempo_viaje_min"] + t2["tiempo_viaje_min"])

    # Regreso a base (incluido)
    regreso_flag = True
    t3 = calcular_ruta(session, destino_norm, base_norm)
    dist_total += float(t3["dist_km"])
    tiempo_total_min += int(t3["tiempo_viaje_min"])

    # Horas reales opcionales
    horas_reales = None
    if body.horas_reales is not None:
        horas_reales = float(body.horas_reales)
    elif body.hora_inicio and body.hora_fin:
        try:
            hi = _parse_hora(body.hora_inicio); hf = _parse_hora(body.hora_fin)
            delta_h = max((hf - hi).total_seconds() / 3600.0, 0)
            horas_reales = round(delta_h, 2)
        except Exception:
            horas_reales = None

    # Buffer por tipo (Si es mudanza puede requerir más, pero lo manejamos con CARGA_DESC_H)
    extra_servicio_min = 0 # Eliminamos el buffer automático para que coincida con Excel

    costos = calcular_costos(
        session=session, # Pasar session
        dist_km=dist_total,
        tiempo_viaje_min=tiempo_total_min,
        ayudante=body.ayudante,
        horas_reales=horas_reales,
        peajes=body.peajes,
        viaticos=float(body.viaticos or 0),
        extra_servicio_min=extra_servicio_min
    )

    # Geocodificación para mayor precisión en mapas/notificaciones
    orig_geo = _geocode_google(origen_norm)
    dest_geo = _geocode_google(destino_norm)

    doc = {
        "nombre_cliente": nombre,
        "telefono": body.telefono,
        "tipo_carga": body.tipo_carga,
        "origen": body.origen,
        "origen_lat": orig_geo["lat"] if orig_geo else None,
        "origen_lng": orig_geo["lng"] if orig_geo else None,
        "destino": body.destino,
        "destino_lat": dest_geo["lat"] if dest_geo else None,
        "destino_lng": dest_geo["lng"] if dest_geo else None,
        "fecha": body.fecha,
        "ayudante": body.ayudante,
        "regreso_base": regreso_flag,
        "hora_inicio": body.hora_inicio,
        "hora_fin": body.hora_fin,
        "horas_reales": horas_reales,
        "peajes": body.peajes,
        "viaticos": body.viaticos,
        "accepted_terms": body.accepted_terms,
        "accepted_terms_at": (body.accepted_terms_at or (datetime.now(timezone.utc) if body.accepted_terms else None)),

        # ✅ AÑADIDO: guardar turno elegido (si viene)
        "fecha_turno": body.fecha_turno,
        "hora_turno": body.hora_turno,

        # totales
        "dist_km": round(dist_total, 3),
        "tiempo_viaje_min": int(tiempo_total_min),
        "tiempo_servicio_min": int(costos["tiempo_servicio_min"]),
        "horas_base": float(costos["horas_base"]),
        # desgloses
        "costo_tiempo_base": float(costos["costo_tiempo_base"]),
        "mantenimiento": float(costos["mantenimiento"]),
        "costo_tiempo": float(costos["costo_tiempo"]),
        "costo_combustible": float(costos["costo_combustible"]),
        "peajes_total": float(costos["peajes_total"]),
        "costo_ayudante": float(costos["costo_ayudante"]),
        "costo_chofer_parcial": float(costos["costo_chofer_parcial"]),
        "costo_admin_parcial": float(costos["costo_admin_parcial"]),
        "monto_estimado": float(costos["monto_estimado"]),
        # tramos
        "tramo_base_origen_km": round(t1["dist_km"], 3),
        "tramo_origen_destino_km": round(t2["dist_km"], 3),
        "tramo_destino_base_km": round(t3["dist_km"], 3),
        "tramo_base_origen_min": int(t1["tiempo_viaje_min"]),
        "tramo_origen_destino_min": int(t2["tiempo_viaje_min"]),
        "tramo_destino_base_min": int(t3["tiempo_viaje_min"]),
        # metadata
        "extra_servicio_min": int(extra_servicio_min),
    }
    return doc

# ⛔ CAMBIO: /api/quote ahora NO persiste; solo devuelve preview
@app.post("/api/quote")
def preview_quote(
    body: QuoteIn,
    session: Session = Depends(get_session)
):
    doc = _calcular_desde_body(session, body)
    # Creamos un objeto dbQuote temporalmente (sin guardar) para serializar
    temp_quote = dbQuote(**doc, estado="preview")
    return {"ok": True, "quote": _quote_public(temp_quote)}

# ✅ Nuevo: enviar y guardar (sin ID previo) + RESERVA ATÓMICA
@app.post("/api/quote/send")
def send_quote_nuevo(
    body: QuoteIn, 
    background: BackgroundTasks, 
    debug: bool = Query(default=False),
    session: Session = Depends(get_session)
):
    """
    Guarda el presupuesto y RESERVA el horario.
    """
    # 1) Requisitos básicos
    if not body.fecha_turno or not body.hora_turno:
        raise HTTPException(status_code=422, detail="Tenés que elegir fecha y horario")

    # 2) Validar que no sea en el pasado
    hoy_ar = datetime.now(AR_TZ)
    try:
        req_dt = datetime.strptime(f"{body.fecha_turno} {body.hora_turno}", "%Y-%m-%d %H:%M").replace(tzinfo=AR_TZ)
        if req_dt < hoy_ar - timedelta(minutes=5):
            raise HTTPException(status_code=409, detail="Ese horario ya pasó")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha/hora inválido")

    # 3) Validar contra overrides del admin
    statement_ovr = select(dbAvailabilityOverride).where(dbAvailabilityOverride.date == body.fecha_turno)
    day_ovr = session.exec(statement_ovr).first()
    
    if day_ovr:
        if not day_ovr.enabled:
            raise HTTPException(status_code=409, detail="El día seleccionado no está habilitado")
        if day_ovr.slots and body.hora_turno not in day_ovr.slots:
            raise HTTPException(status_code=409, detail="El horario ya no está disponible")
    else:
        if body.hora_turno not in DEFAULT_SLOTS:
            raise HTTPException(status_code=409, detail="Horario no válido para este servicio")

    # 4) RESERVA en la tabla bookings
    # Verificamos si ya existe un booking para esa fecha/hora con estado reserved o confirmed
    statement_check = select(dbBooking).where(
        dbBooking.date == body.fecha_turno,
        dbBooking.time == body.hora_turno,
        dbBooking.status.in_(["reserved", "confirmed"])
    )
    existing = session.exec(statement_check).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ese horario ya fue reservado por otra persona")

    try:
        booking = dbBooking(
            quote_id="PENDING",
            date=body.fecha_turno,
            time=body.hora_turno,
            status="reserved"
        )
        session.add(booking)
        session.commit() # Flush inicial para asegurar reserva
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=409, detail="Ese horario ya fue reservado (error de concurrencia)")

    # 5) Sincronizar 'availability' (si el admin puso slots específicos, lo sacamos de la lista)
    if day_ovr and day_ovr.slots:
        if body.hora_turno in day_ovr.slots:
            new_slots = [s for s in day_ovr.slots if s != body.hora_turno]
            day_ovr.slots = new_slots
            session.add(day_ovr)

    # 6) Calcular y guardar presupuesto
    try:
        data = _calcular_desde_body(session, body)
        quote = dbQuote(**data, estado="sent")
        session.add(quote)
        session.commit()
        session.refresh(quote)
        
        # Actualizar el booking con el ID real
        booking.quote_id = str(quote.id)
        session.add(booking)
        session.commit()
        
    except Exception as e:
        # Rollback del booking en caso de error
        session.delete(booking)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Error al procesar presupuesto: {str(e)}")

    # 7) Notificar
    doc_dict = quote.model_dump()
    if debug:
        res = _notify_new_quote(doc_dict)
    else:
        background.add_task(_notify_new_quote, doc_dict)
        res = None

    pub = _quote_public(quote)
    pub["contact_urls"] = _contact_urls(str(quote.id))
    return {"ok": True, "quote": pub, "notify": res} if debug else {"ok": True, "quote": pub}

# (Compat) Enviar por ID existente (sigue funcionando si lo usabas en admin)
@app.post("/api/quote/{quote_id}/send")
def send_quote(
    quote_id: str, 
    background: BackgroundTasks, 
    debug: bool = Query(default=False),
    session: Session = Depends(get_session)
):
    try:
        qid = int(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    quote = session.get(dbQuote, qid)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    if quote.estado == "cancelado":
        raise HTTPException(status_code=409, detail="El presupuesto fue cancelado")

    if quote.estado != "sent":
        quote.estado = "sent"
        quote.sent_at = datetime.now(timezone.utc)
        session.add(quote)
        session.commit()
        session.refresh(quote)

    doc_dict = quote.model_dump()
    if debug:
        res = _notify_new_quote(doc_dict)
        pub = _quote_public(quote)
        pub["contact_urls"] = _contact_urls(quote_id)
        return {"ok": True, "quote": pub, "notify": res}

    background.add_task(_notify_new_quote, doc_dict)
    pub = _quote_public(quote)
    pub["contact_urls"] = _contact_urls(quote_id)
    return {"ok": True, "quote": pub}

@app.post("/api/quote/{quote_id}/cancel")
def cancel_quote(
    quote_id: str,
    session: Session = Depends(get_session)
):
    try:
        qid = int(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    quote = session.get(dbQuote, qid)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    quote.estado = "cancelado"
    quote.cancelled_at = datetime.now(timezone.utc)
    session.add(quote)
    session.commit()
    session.refresh(quote)
    
    return {"ok": True, "quote": _quote_public(quote)}

@app.post("/api/quotes/{quote_id}/confirm")
def confirmar_quote(
    quote_id: str, 
    body: ConfirmPayload = Body(default=None), 
    background: BackgroundTasks = None,
    session: Session = Depends(get_session)
):
    try:
        qid = int(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    quote = session.get(dbQuote, qid)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if quote.estado != "confirmado":
        quote.estado = "confirmado"
        quote.confirmado_en = datetime.now(timezone.utc)
        if body:
            quote.fecha_hora_preferida = body.fecha_hora_preferida
            quote.notas_confirmacion = body.notas
        session.add(quote)
        session.commit()
        session.refresh(quote)

    # ✅ marcar booking como confirmado (si existe)
    try:
        ft = quote.fecha_turno
        ht = quote.hora_turno
        if ft and ht:
            statement_b = select(dbBooking).where(
                dbBooking.quote_id == str(quote.id),
                dbBooking.date == ft,
                dbBooking.time == ht
            )
            booking = session.exec(statement_b).first()
            if booking:
                booking.status = "confirmed"
                booking.confirmed_at = datetime.now(timezone.utc)
                session.add(booking)
            else:
                # Fallback: crear booking si no existía (raro pero posible en migración)
                booking = dbBooking(
                    quote_id=str(quote.id),
                    date=ft,
                    time=ht,
                    status="confirmed",
                    confirmed_at=datetime.now(timezone.utc)
                )
                session.add(booking)
            session.commit()
    except Exception as e:
        print(f"Error confirmando booking: {e}")

    doc_dict = quote.model_dump()
    if background:
        background.add_task(_notify_confirmed_quote, doc_dict)
    else:
        _notify_confirmed_quote(doc_dict)

    return {"ok": True, "quote": _quote_public(quote)}


# =========================
# Login seguro + rate limit
# =========================
@app.post("/api/login", response_model=LoginOut)
@limiter.limit("5/minute")
async def admin_login(
    request: Request, 
    body: LoginIn,
    session: Session = Depends(get_session)
):
    username = (body.username or "").strip().lower()
    password = (body.password or "").strip()

    if not username or not password:
        raise HTTPException(status_code=422, detail="Faltan 'username/email' y/o 'password'")

    statement = select(dbUser).where(
        (dbUser.email == username) | (dbUser.username == username)
    )
    user = session.exec(statement).first()

    import traceback
    try:
        if not user and username == (os.getenv("ADMIN_USER","admin")).lower() and password == os.getenv("ADMIN_PASS","admin123"):
            token = os.urandom(16).hex()
            expira = datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("SESSION_DURATION_MIN", "120")))
            return LoginOut(ok=True, message=f"Login exitoso (modo .env). Expira a las {expira.strftime('%H:%M')}", token=token)

        if not user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        # Asegurar que el objeto está vinculado a la sesión actual
        session.add(user)

        # 2) Verificar bloqueo
        try:
            check_lock(user)
        except PermissionError as e:
            raise HTTPException(status_code=429, detail=str(e))

        # 3) Verificar password
        if not verify_password(user.password_hash or "", password):
            register_fail(session, user)
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        # 4) Success
        reset_fail(session, user)

        token = os.urandom(16).hex()
        expira = datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("SESSION_DURATION_MIN", "120")))
        return LoginOut(ok=True, message=f"Login exitoso. Expira a las {expira.strftime('%H:%M')}", token=token)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Error] admin_login critical failure: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ratelimit-test")
@limiter.limit("10/minute")
async def ratelimit_test(request: Request):
    return {"ok": True}


# =========================
# Admin (listado simple)
# =========================
def _serialize_quote(doc: dbQuote) -> dict:
    d = _quote_public(doc)
    d.update({
        "tramo_base_origen_km": float(doc.tramo_base_origen_km),
        "tramo_origen_destino_km": float(doc.tramo_origen_destino_km),
        "tramo_destino_base_km": float(doc.tramo_destino_base_km),
        "tramo_base_origen_min": int(doc.tramo_base_origen_min),
        "tramo_origen_destino_min": int(doc.tramo_origen_destino_min),
        "tramo_destino_base_min": int(doc.tramo_destino_base_min),
        "created_at": (doc.created_at or datetime.now(timezone.utc)).isoformat(),
        "extra_servicio_min": int(doc.extra_servicio_min),
        "costo_tiempo_base": float(doc.costo_tiempo_base),
        "mantenimiento": float(doc.mantenimiento),
        "costo_ayudante": float(doc.costo_ayudante),
        "peajes_total": float(doc.peajes_total),
        # ✅ mostrar turno en admin
        "fecha_turno": doc.fecha_turno,
        "hora_turno": doc.hora_turno,
    })
    return d

# ✅ AHORA REQUIERE TOKEN (tu frontend ya lo manda)
from datetime import timezone as dt_timezone  # arriba ya importaste timezone, esto es opcional

@app.get("/api/requests")
def listar_requests(
    status: str = Query(default="pending", description="pending | historicos | all"),
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    # 1) marcar realizados (confirmados vencidos)
    _marcar_realizados(session)

    # 2) hoy AR (YYYY-MM-DD)
    today_str = _today_ar_str()
    st = (status or "pending").strip().lower()

    # 3) autolimpieza: borrar NO confirmados vencidos
    #    (sent o rechazado) -> se borran solos cuando ya pasó la fecha_turno
    statement_del = select(dbQuote).where(
        dbQuote.estado.in_(["sent", "rechazado"]),
        dbQuote.fecha_turno < today_str
    )
    to_delete = session.exec(statement_del).all()
    for q in to_delete:
        session.delete(q)
    if to_delete:
        session.commit()

    # 4) Construir filtro según estado solicitado
    if st == "pending":
        statement = select(dbQuote).where(
            dbQuote.estado.in_(["sent", "rechazado", "confirmado"]),
            (dbQuote.fecha_turno >= today_str) | (dbQuote.fecha_turno == None)
        ).order_by(dbQuote.created_at.desc())

    elif st == "historicos":
        # Incluye realizados y anulados
        statement = select(dbQuote).where(
            dbQuote.estado.in_(["realizado", "anulado", "cancelado"])
        ).order_by(dbQuote.created_at.desc())

    elif st == "all":
        statement = select(dbQuote).order_by(dbQuote.created_at.desc())

    else:
        raise HTTPException(status_code=400, detail="status inválido. Usar pending | historicos | all")

    quotes_list = session.exec(statement).all()
    items = [_serialize_quote(q) for q in quotes_list]

    return {"items": items, "status": st, "today": today_str}

@app.post("/api/requests/{quote_id}/confirm")
def admin_confirmar(
    quote_id: str, 
    background: BackgroundTasks, 
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    try:
        qid = int(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    
    quote = session.get(dbQuote, qid)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    quote.estado = "confirmado"
    quote.confirmado_en = datetime.now(timezone.utc)
    session.add(quote)
    session.commit()
    session.refresh(quote)
    
    # ✅ marcar booking como confirmado
    try:
        ft = quote.fecha_turno
        ht = quote.hora_turno
        if ft and ht:
            statement_b = select(dbBooking).where(
                dbBooking.quote_id == str(quote.id),
                dbBooking.date == ft,
                dbBooking.time == ht
            )
            booking = session.exec(statement_b).first()
            if booking:
                booking.status = "confirmed"
                booking.confirmed_at = datetime.now(timezone.utc)
                session.add(booking)
                session.commit()
    except Exception as e:
        print(f"Error confirmando booking: {e}")

    background.add_task(_notify_confirmed_quote, quote.model_dump())

    return {"message": "Presupuesto confirmado"}

@app.post("/api/requests/{quote_id}/complete")
def admin_completar(
    quote_id: str, 
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    try:
        qid = int(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    quote = session.get(dbQuote, qid)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    quote.estado = "realizado"
    quote.completed_at = datetime.now(timezone.utc)
    session.add(quote)
    
    # Actualizar booking a completed
    statement_b = select(dbBooking).where(dbBooking.quote_id == str(quote.id))
    bookings_list = session.exec(statement_b).all()
    for b in bookings_list:
        b.status = "completed"
        session.add(b)
        
    session.commit()
    return {"message": "Trabajo completado"}

@app.post("/api/requests/{quote_id}/void")
def admin_anular(
    quote_id: str, 
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    try:
        qid = int(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    quote = session.get(dbQuote, qid)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    quote.estado = "anulado"
    quote.voided_at = datetime.now(timezone.utc)
    session.add(quote)

    # LIBERAR el slot del calendario (borrar booking)
    statement_b = select(dbBooking).where(dbBooking.quote_id == str(quote.id))
    bookings_list = session.exec(statement_b).all()
    for b in bookings_list:
        session.delete(b)
    
    # Si había override manual en availability, devolver el slot
    ft = quote.fecha_turno
    ht = quote.hora_turno
    if ft and ht:
        statement_ovr = select(dbAvailabilityOverride).where(dbAvailabilityOverride.date == ft)
        day_ovr = session.exec(statement_ovr).first()
        if day_ovr and day_ovr.slots:
            if ht not in day_ovr.slots:
                day_ovr.slots.append(ht)
                session.add(day_ovr)

    session.commit()
    return {"message": "Presupuesto anulado y horario liberado"}

@app.post("/api/requests/{quote_id}/reject")
def admin_rechazar(
    quote_id: str, 
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    try:
        qid = int(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    quote = session.get(dbQuote, qid)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    quote.estado = "rechazado"
    # El campo updated_at no existe en dbQuote, lo omitimos o lo agregamos después si es necesario
    session.add(quote)
    session.commit()

    return {"message": "Presupuesto rechazado"}

@app.delete("/api/requests/{quote_id}")
def admin_eliminar(
    quote_id: str, 
    user=Depends(require_api_key),
    session: Session = Depends(get_session)
):
    try:
        qid = int(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    quote = session.get(dbQuote, qid)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    # ✅ recuperar turno antes de borrar
    ft = quote.fecha_turno
    ht = quote.hora_turno

    # ✅ borrar quote
    session.delete(quote)

    # ✅ Liberar horario
    if ft and ht:
        # 1) Borrar booking
        statement_b = select(dbBooking).where(dbBooking.quote_id == str(qid))
        bs = session.exec(statement_b).all()
        for b in bs:
            session.delete(b)
            
        # 2) Devolver a 'availability' SOLO si el día ya tenía configuración custom
        statement_ovr = select(dbAvailabilityOverride).where(dbAvailabilityOverride.date == ft)
        day_ovr = session.exec(statement_ovr).first()
        if day_ovr and day_ovr.slots:
            if ht not in day_ovr.slots:
                day_ovr.slots.append(ht)
                session.add(day_ovr)

    session.commit()
    return {"message": "Eliminado y turno liberado" if (ft and ht) else "Eliminado"}


# ✅ 2) recién DESPUÉS tu catch-all para el SPA
@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith(("api", "static", "images")):
        raise HTTPException(status_code=404, detail="API route not found")
    return FileResponse(FRONT_DIR / "index.html")


# =========================
# Runner local
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.backend:app", host="127.0.0.1", port=8000, reload=True)
