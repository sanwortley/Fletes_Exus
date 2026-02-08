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
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
load_dotenv(override=True)

# FRONTEND
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

# Notificaciones (tu módulo existente)
from .notifications import send_whatsapp_to_javier

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

# SOLO assets
app.mount("/static", StaticFiles(directory=FRONT_DIR / "static"), name="static")
app.mount("/images", StaticFiles(directory=FRONT_DIR / "images"), name="images")


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
# MongoDB
# =========================
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Falta MONGO_URI en variables de entorno")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client["fletes_db"]
quotes = db["quotes"]
users = db["users"]

# ✅ AÑADIDO: colecciones agenda
availability = db["availability"]
bookings = db["bookings"]

DEFAULT_SLOTS = [
    "08:00", "09:00", "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00", "16:00", "17:00",
    "18:00", "19:00", "20:00", "21:00", "22:00"
]

# ✅ índices útiles
try:
    availability.create_index("date", unique=True)
    bookings.create_index([("date", 1), ("time", 1)], unique=True)
except Exception:
    pass

@app.on_event("startup")
def _on_startup():
    try:
        client.admin.command("ping")
        print("[Mongo] Atlas OK 🚀")
    except Exception as e:
        print("[Mongo] ERROR:", e)

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

KM_POR_LITRO = float(os.getenv("KM_POR_LITRO", "8"))
COSTO_LITRO = float(os.getenv("COSTO_LITRO", "1600"))
COSTO_HORA = float(os.getenv("COSTO_HORA", "25000"))
COSTO_HORA_AYUDANTE = float(os.getenv("COSTO_HORA_AYUDANTE", "10000"))
FACTOR_PONDERACION = float(os.getenv("FACTOR_PONDERACION", "1.5"))

FACTOR_TRAZADO = float(os.getenv("FACTOR_TRAZADO", "1.25"))
VEL_KMH = float(os.getenv("VEL_KMH", "35"))

MANTENIMIENTO_POR_KM = float(os.getenv("MANTENIMIENTO_POR_KM", "0"))
MANTENIMIENTO_PCT = float(os.getenv("MANTENIMIENTO_PCT", "0.20"))
COSTO_PEAJE = float(os.getenv("COSTO_PEAJE", "2000"))
COSTO_CHOFER_HORA = float(os.getenv("COSTO_CHOFER_HORA", "7500"))
COSTO_ADMIN_HORA = float(os.getenv("COSTO_ADMIN_HORA", "3500"))

REDONDEO_MIN = int(os.getenv("REDONDEO_MIN", "30"))
BASE_FIJA = float(os.getenv("BASE_FIJA", "0"))
MIN_TOTAL = float(os.getenv("MIN_TOTAL", "0"))
INCLUIR_AYUDANTE_EN_TOTAL = (os.getenv("INCLUIR_AYUDANTE_EN_TOTAL", "1") == "1")
RETURN_TO_BASE_DEFAULT = (os.getenv("RETURN_TO_BASE_DEFAULT", "0") == "1")
EXCEL_MODE = (os.getenv("EXCEL_MODE", "0") == "1")
CARGA_DESC_H = float(os.getenv("CARGA_DESC_H", "0"))
COSTO_COMBUSTIBLE_KM = float(os.getenv("COSTO_COMBUSTIBLE_KM", "0"))
INCLUIR_CHOFER_ADMIN_EN_TOTAL = (os.getenv("INCLUIR_CHOFER_ADMIN_EN_TOTAL", "0") == "1")

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

def _distance_time_fallback(origen: str, destino: str) -> Dict[str, Any]:
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

def _purge_expired_unconfirmed():
    hoy = _today_ar_str()

    expired = list(quotes.find(
        {"estado": {"$in": ["sent", "rechazado"]}, "fecha_turno": {"$lt": hoy}},
        {"_id": 1}
    ))

    if not expired:
        return 0

    ids = [d["_id"] for d in expired]
    quotes.delete_many({"_id": {"$in": ids}})
    return len(ids)



def _marcar_realizados():
    hoy = _today_ar_str()

    # Confirmado + fecha_turno pasada => Realizado
    quotes.update_many(
        {
            "estado": "confirmado",
            "fecha_turno": {"$lt": hoy}
        },
        {
            "$set": {
                "estado": "realizado",
                "realizado_en": datetime.now(timezone.utc)
            }
        }
    )


def calcular_ruta(origen: str, destino: str) -> Dict[str, Any]:
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
        res = _distance_time_fallback(origen, destino); used = "fallback(heuristica_10km)"
    print(f"[route] provider_used={used} origen='{origen}' destino='{destino}' -> {res}")
    return res

# =========================
# Cálculo de costos
# =========================
def calcular_costos(
    dist_km: float,
    tiempo_viaje_min: int,
    ayudante: bool,
    horas_reales: Optional[float] = None,
    peajes: int = 0,
    viaticos: float = 0.0,
    extra_servicio_min: int = 0,
) -> Dict[str, float]:

    # 1) Horas base (manejo)
    horas_manejo = (horas_reales if horas_reales and horas_reales > 0 else (tiempo_viaje_min / 60.0))

    # 2) Tiempo total estilo Excel:
    #    (horas + min/60) * ponderación + carga/descarga(extra)
    horas_total = (horas_manejo * FACTOR_PONDERACION) + (extra_servicio_min / 60.0)

    # 3) Redondeo por bloques (si querés que sea igual que la planilla, lo podés dejar)
    if REDONDEO_MIN > 0:
        import math
        bloque_h = REDONDEO_MIN / 60.0
        horas_total = bloque_h * math.ceil(horas_total / bloque_h)

    # 4) Costos por tiempo
    costo_tiempo = horas_total * COSTO_HORA
    costo_chofer_parcial = horas_total * COSTO_CHOFER_HORA
    costo_admin_parcial = horas_total * COSTO_ADMIN_HORA
    costo_ayudante = horas_total * COSTO_HORA_AYUDANTE if ayudante else 0.0

    # 5) Combustible + mantenimiento (para que te dé como el Excel)
    costo_combustible = (dist_km / max(KM_POR_LITRO, 0.1)) * COSTO_LITRO

    # ✅ IMPORTANTE: tu Excel está metiendo mantenimiento como “$ por km”
    mantenimiento = dist_km * MANTENIMIENTO_POR_KM

    peajes_total = peajes * COSTO_PEAJE

    # 6) Total
    monto_estimado = (
        BASE_FIJA
        + costo_tiempo
        + costo_combustible
        + mantenimiento
        + peajes_total
        + viaticos
    )

    if INCLUIR_AYUDANTE_EN_TOTAL and ayudante:
        monto_estimado += costo_ayudante

    monto_estimado = max(monto_estimado, MIN_TOTAL)

    return {
        "horas_base": round(horas_total, 2),
        "tiempo_servicio_min": int(round(horas_total * 60)),
        "costo_tiempo_base": round(costo_tiempo, 2),
        "mantenimiento": round(mantenimiento, 2),
        "costo_tiempo": round(costo_tiempo, 2),
        "costo_combustible": round(costo_combustible, 2),
        "peajes_total": round(peajes_total, 2),
        "viaticos": round(viaticos, 2),
        "costo_ayudante": round(costo_ayudante, 2),
        "costo_chofer_parcial": round(costo_chofer_parcial, 2),
        "costo_admin_parcial": round(costo_admin_parcial, 2),
        "monto_estimado": round(monto_estimado, 2),
    }

# =========================
# Serializaciones
# =========================
def _quote_public(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]) if doc.get("_id") else None,
        "nombre_cliente": doc.get("nombre_cliente"),
        "telefono": doc.get("telefono"),
        "tipo_carga": doc.get("tipo_carga"),
        "origen": doc.get("origen"),
        "destino": doc.get("destino"),
        "fecha": doc.get("fecha"),
        "ayudante": bool(doc.get("ayudante")),
        "regreso_base": bool(doc.get("regreso_base", False)),
        "dist_km": float(doc.get("dist_km", 0)),
        "tiempo_viaje_min": int(doc.get("tiempo_viaje_min", 0)),
        "tiempo_servicio_min": int(doc.get("tiempo_servicio_min", 0)),
        "costo_tiempo": float(doc.get("costo_tiempo", 0)),
        "costo_combustible": float(doc.get("costo_combustible", 0)),
        "monto_estimado": float(doc.get("monto_estimado", 0)),
        "estado": doc.get("estado", "preview"),

        # ✅ AÑADIDO: exponer turno (para que lo muestres en UI/admin)
        "fecha_turno": doc.get("fecha_turno"),
        "hora_turno": doc.get("hora_turno"),
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
    try:
        text = format_whatsapp_quote(doc)
        wa_res = send_whatsapp_to_javier(text)
    except Exception as e:
        wa_res = {"ok": "false", "error": str(e)}
    return {"whatsapp": wa_res}

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
def get_availability(month: str = Query(..., description="YYYY-MM")):
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
    overrides = {d["date"]: d for d in availability.find({"date": {"$gte": start, "$lte": end}})}
    
    # 2) Obtener bookings (reservados o confirmados)
    booked = {}
    for b in bookings.find({"date": {"$gte": start, "$lte": end}, "status": {"$in": ["reserved", "confirmed"]}}):
        d_key = b["date"]
        booked.setdefault(d_key, set()).add(b["time"])

    # 3) Construir respuesta (solo devolvemos días que tengan algún cambio respecto al default)
    #    Si no está en la respuesta, el frontend usa defaultSlots.
    days: Dict[str, List[str]] = {}
    
    # Iteramos todos los días del mes para asegurar consistencia
    for d in range(1, last_day + 1):
        date_str = f"{year:04d}-{mon:02d}-{d:02d}"
        
        # Base: lo que el admin configuró o el default
        day_ovr = overrides.get(date_str)
        if day_ovr and not day_ovr.get("enabled", True):
            # Día deshabilitado completamente
            days[date_str] = []
            continue
            
        base_slots = day_ovr.get("slots") if (day_ovr and "slots" in day_ovr) else DEFAULT_SLOTS
        
        # Restar bookings
        day_booked = booked.get(date_str, set())
        final_slots = [s for s in base_slots if s not in day_booked]
        
        # Si el resultado es distinto al DEFAULT_SLOTS original, lo enviamos
        # (O si preferís enviar todo para ser explícito, también vale)
        if sorted(final_slots) != sorted(DEFAULT_SLOTS):
            days[date_str] = final_slots

    return {"ok": True, "month": month, "days": days}

@app.get("/api/admin/availability")
def admin_get_availability(month: str = Query(..., description="YYYY-MM"), user=Depends(require_api_key)):
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

    items = list(availability.find({"date": {"$gte": start, "$lte": end}}, {"_id": 0}))
    return {"ok": True, "month": month, "items": items}

@app.post("/api/availability/day")
def upsert_availability_day(body: AvailabilityDayIn, user=Depends(require_api_key)):

    if not body.date or not isinstance(body.slots, list):
        raise HTTPException(status_code=400, detail="Se requiere 'date' y 'slots' (lista)")

    # 🔒 1) Buscar horarios ya reservados o confirmados
    ocupados = set(
        b["time"] for b in bookings.find(
            {
                "date": body.date,
                "status": {"$in": ["reserved", "confirmed"]}
            },
            {"_id": 0, "time": 1}
        )
    )

    # 🔒 2) Filtrar slots enviados por el admin
    slots_validos = [s for s in body.slots if s not in ocupados]

    availability.update_one(
        {"date": body.date},
        {"$set": {
            "date": body.date,
            "enabled": bool(body.enabled),
            "slots": slots_validos,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True
    )

    return {
        "ok": True,
        "bloqueados": list(ocupados),
        "slots_guardados": slots_validos
    }


@app.get("/api/admin/bookings/day")
def admin_get_bookings_day(date: str = Query(..., description="YYYY-MM-DD"), user=Depends(require_api_key)):
    """
    Devuelve horarios ocupados (reserved/confirmed) para bloquearlos en el panel de disponibilidad.
    """
    if not date or len(date) != 10:
        raise HTTPException(status_code=400, detail="date inválida. Usar YYYY-MM-DD")

    ocupados = sorted(list(set(
        b["time"] for b in bookings.find(
            {"date": date, "status": {"$in": ["reserved", "confirmed"]}},
            {"_id": 0, "time": 1}
        )
        if b.get("time")
    )))

    return {"ok": True, "date": date, "ocupados": ocupados}

# =========================
# Rutas core
# =========================
@app.get("/api/config")
def get_config():
    return {
        "google_maps_api_key": GOOGLE_MAPS_API_KEY,
        "default_locality": DEFAULT_LOCALITY,
        "maps_region": MAPS_REGION,
        "maps_language": MAPS_LANGUAGE
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Fletes Javier API"}

def _calcular_desde_body(body: QuoteIn) -> dict:
    # Normalizar
    nombre = body.nombre_cliente or body.__dict__.get("nombre_cliente")
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta nombre_cliente")

    origen_norm = _normalize_addr(body.origen)
    destino_norm = _normalize_addr(body.destino)
    base_norm = _normalize_addr(BASE_DIRECCION)

    # Tramos
    t1 = calcular_ruta(base_norm, origen_norm)
    t2 = calcular_ruta(origen_norm, destino_norm)

    dist_total = float(t1["dist_km"] + t2["dist_km"])
    tiempo_total_min = int(t1["tiempo_viaje_min"] + t2["tiempo_viaje_min"])

    # Regreso a base (incluido)
    regreso_flag = True
    t3 = calcular_ruta(destino_norm, base_norm)
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

    # Buffer por tipo
    is_mudanza = "mudanza" in (body.tipo_carga or "").lower()
    extra_servicio_min = 60 if is_mudanza else 30

    costos = calcular_costos(
        dist_total, tiempo_total_min, body.ayudante,
        horas_reales=horas_reales, peajes=body.peajes, viaticos=body.viaticos,
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
def preview_quote(body: QuoteIn):
    doc = _calcular_desde_body(body)
    doc["estado"] = "preview"
    return {"ok": True, "quote": _quote_public(doc)}

# ✅ Nuevo: enviar y guardar (sin ID previo) + RESERVA ATÓMICA
@app.post("/api/quote/send")
def send_quote_nuevo(body: QuoteIn, background: BackgroundTasks, debug: bool = Query(default=False)):
    """
    Guarda el presupuesto y RESERVA el horario de forma atómica.
    Válido para horarios por defecto o configurados por admin.
    """
    # 1) Requisitos básicos
    if not body.fecha_turno or not body.hora_turno:
        raise HTTPException(status_code=422, detail="Tenés que elegir fecha y horario")

    # 2) Validar que no sea en el pasado (Hoy o Futuro)
    hoy_ar = datetime.now(AR_TZ)
    try:
        req_dt = datetime.strptime(f"{body.fecha_turno} {body.hora_turno}", "%Y-%m-%d %H:%M").replace(tzinfo=AR_TZ)
        if req_dt < hoy_ar - timedelta(minutes=5): # Margen de 5 min
            raise HTTPException(status_code=409, detail="Ese horario ya pasó")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha/hora inválido")

    # 3) Validar contra overrides del admin (Habilitado/Deshabilitado o slots específicos)
    day_ovr = availability.find_one({"date": body.fecha_turno})
    if day_ovr:
        if not day_ovr.get("enabled", True):
            raise HTTPException(status_code=409, detail="El día seleccionado no está habilitado")
        
        # Si el admin definió un set específico de slots para ese día
        if "slots" in day_ovr:
            if body.hora_turno not in day_ovr["slots"]:
                raise HTTPException(status_code=409, detail="El horario ya no está disponible (cambio del admin)")
    else:
        # Si no hay override, validamos contra los defaults globales
        if body.hora_turno not in DEFAULT_SLOTS:
            raise HTTPException(status_code=409, detail="Horario no válido para este servicio")

    # 4) RESERVA ATÓMICA en la colección bookings (gracias al índice único)
    try:
        bookings.insert_one({
            "quote_id": "PENDING", # Se actualizará luego
            "date": body.fecha_turno,
            "time": body.hora_turno,
            "status": "reserved",
            "created_at": datetime.now(timezone.utc),
        })
    except Exception: # Puede ser DuplicateKeyError
        raise HTTPException(status_code=409, detail="Ese horario ya fue reservado por otra persona")

    # 5) Sincronizar 'availability' (si el admin puso slots específicos, lo sacamos de la lista)
    if day_ovr and "slots" in day_ovr:
         availability.update_one(
            {"date": body.fecha_turno},
            {"$pull": {"slots": body.hora_turno}}
        )

    # 6) Calcular y guardar presupuesto
    try:
        doc = _calcular_desde_body(body)
        doc["estado"] = "sent"
        doc["created_at"] = datetime.now(timezone.utc)
        
        _id = quotes.insert_one(doc).inserted_id
        doc["_id"] = _id
        
        # Actualizar el booking con el ID real
        bookings.update_one(
            {"date": body.fecha_turno, "time": body.hora_turno, "quote_id": "PENDING"},
            {"$set": {"quote_id": str(_id)}}
        )
    except Exception as e:
        # Rollback del booking en caso de error catastrófico al guardar el quote
        bookings.delete_one({"date": body.fecha_turno, "time": body.hora_turno, "quote_id": "PENDING"})
        raise HTTPException(status_code=500, detail=f"Error al procesar presupuesto: {str(e)}")

    # 7) Notificar
    if debug:
        res = _notify_new_quote(doc)
    else:
        background.add_task(_notify_new_quote, doc)
        res = None

    pub = _quote_public(doc)
    pub["contact_urls"] = _contact_urls(str(_id))
    return {"ok": True, "quote": pub, "notify": res} if debug else {"ok": True, "quote": pub}

# (Compat) Enviar por ID existente (sigue funcionando si lo usabas en admin)
@app.post("/api/quote/{quote_id}/send")
def send_quote(quote_id: str, background: BackgroundTasks, debug: bool = Query(default=False)):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    doc = quotes.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    if doc.get("estado") == "cancelado":
        raise HTTPException(status_code=409, detail="El presupuesto fue cancelado")

    if doc.get("estado") != "sent":
        quotes.update_one({"_id": _id}, {"$set": {"estado": "sent", "sent_at": datetime.now(timezone.utc)}})
        doc = quotes.find_one({"_id": _id})

    if debug:
        res = _notify_new_quote(doc)
        pub = _quote_public(doc)
        pub["estado"] = "sent"
        pub["contact_urls"] = _contact_urls(quote_id)
        return {"ok": True, "quote": pub, "notify": res}

    background.add_task(_notify_new_quote, doc)
    pub = _quote_public(doc)
    pub["estado"] = "sent"
    pub["contact_urls"] = _contact_urls(quote_id)
    return {"ok": True, "quote": pub}

@app.post("/api/quote/{quote_id}/cancel")
def cancel_quote(quote_id: str):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    doc = quotes.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    quotes.update_one({"_id": _id}, {"$set": {"estado": "cancelado", "cancelled_at": datetime.now(timezone.utc)}})
    doc = quotes.find_one({"_id": _id})
    return {"ok": True, "quote": _quote_public(doc)}

@app.post("/api/quotes/{quote_id}/confirm")
def confirmar_quote(quote_id: str, body: ConfirmPayload = Body(default=None), background: BackgroundTasks = None):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    doc = quotes.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if doc.get("estado") != "confirmado":
        quotes.update_one({"_id": _id}, {"$set": {
            "estado": "confirmado",
            "confirmado_en": datetime.now(timezone.utc),
            "fecha_hora_preferida": (body.fecha_hora_preferida if body else None),
            "notas_confirmacion": (body.notas if body else None)
        }})
        doc = quotes.find_one({"_id": _id})

    # ✅ marcar booking como confirmado (si existe)
    try:
        ft = doc.get("fecha_turno")
        ht = doc.get("hora_turno")
        if ft and ht:
            bookings.update_one(
                {"quote_id": str(_id), "date": ft, "time": ht},
                {"$set": {"status": "confirmed", "confirmed_at": datetime.now(timezone.utc)}},
                upsert=True
            )
    except Exception:
        pass

    if background:
        background.add_task(_notify_confirmed_quote, doc)

    else:
        _notify_confirmed_quote(doc)


    return {"ok": True, "quote": _quote_public(doc)}


# =========================
# Login seguro + rate limit
# =========================
@app.post("/api/login", response_model=LoginOut)
@limiter.limit("5/minute")
async def admin_login(request: Request, body: LoginIn):
    username = (body.username or "").strip().lower()
    password = (body.password or "").strip()

    if not username or not password:
        raise HTTPException(status_code=422, detail="Faltan 'username/email' y/o 'password'")

    user = users.find_one({"email": username}) or users.find_one({"username": username})

    if not user and username == (os.getenv("ADMIN_USER","admin")).lower() and password == os.getenv("ADMIN_PASS","admin123"):
        token = os.urandom(16).hex()
        expira = datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("SESSION_DURATION_MIN", "120")))
        return LoginOut(ok=True, message=f"Login exitoso (modo .env). Expira a las {expira.strftime('%H:%M')}", token=token)

    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    try:
        check_lock(user)
    except PermissionError as e:
        raise HTTPException(status_code=429, detail=str(e))

    if not verify_password(user.get("password_hash", ""), password):
        register_fail(users, user)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    reset_fail(users, user["_id"])

    token = os.urandom(16).hex()
    expira = datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("SESSION_DURATION_MIN", "120")))
    return LoginOut(ok=True, message=f"Login exitoso. Expira a las {expira.strftime('%H:%M')}", token=token)

@app.get("/api/ratelimit-test")
@limiter.limit("10/minute")
async def ratelimit_test(request: Request):
    return {"ok": True}


# =========================
# Admin (listado simple)
# =========================
def _serialize_quote(doc: dict) -> dict:
    d = _quote_public(doc)
    d.update({
        "tramo_base_origen_km": float(doc.get("tramo_base_origen_km", 0)),
        "tramo_origen_destino_km": float(doc.get("tramo_origen_destino_km", 0)),
        "tramo_destino_base_km": float(doc.get("tramo_destino_base_km", 0)),
        "tramo_base_origen_min": int(doc.get("tramo_base_origen_min", 0)),
        "tramo_origen_destino_min": int(doc.get("tramo_origen_destino_min", 0)),
        "tramo_destino_base_min": int(doc.get("tramo_destino_base_min", 0)),
        "created_at": (doc.get("created_at") or datetime.now(timezone.utc)).isoformat(),
        "extra_servicio_min": int(doc.get("extra_servicio_min", 0)),
        "costo_tiempo_base": float(doc.get("costo_tiempo_base", 0)),
        "mantenimiento": float(doc.get("mantenimiento", 0)),
        "costo_ayudante": float(doc.get("costo_ayudante", 0)),
        "peajes_total": float(doc.get("peajes_total", 0)),
        # ✅ mostrar turno en admin
        "fecha_turno": doc.get("fecha_turno"),
        "hora_turno": doc.get("hora_turno"),
    })
    return d

# ✅ AHORA REQUIERE TOKEN (tu frontend ya lo manda)
from datetime import timezone as dt_timezone  # arriba ya importaste timezone, esto es opcional

@app.get("/api/requests")
def listar_requests(
    status: str = Query(default="pending", description="pending | historicos | all"),
    user=Depends(require_api_key)
):
    # 1) marcar realizados (confirmados vencidos)
    _marcar_realizados()

    # 2) hoy AR (YYYY-MM-DD)
    today_str = _today_ar_str()
    st = (status or "pending").strip().lower()

    # 3) autolimpieza: borrar NO confirmados vencidos
    #    (sent o rechazado) -> se borran solos cuando ya pasó la fecha_turno
    #    ⚠️ NO liberar horarios acá (para Opción A)
    quotes.delete_many({
        "estado": {"$in": ["sent", "rechazado"]},
        "fecha_turno": {"$lt": today_str}
    })

    if st == "pending":
        base_filter = {
            "estado": {"$in": ["sent", "rechazado", "confirmado"]},
            "$or": [
                {"fecha_turno": {"$gte": today_str}},
                {"fecha_turno": {"$exists": False}},
                {"fecha_turno": None},
            ]
        }

    elif st == "historicos":
        # Incluye realizados y anulados
        base_filter = {"estado": {"$in": ["realizado", "anulado"]}}

    elif st == "all":
        base_filter = {}

    else:
        raise HTTPException(status_code=400, detail="status inválido. Usar pending | historicos | all")

    items: List[dict] = []
    for doc in quotes.find(base_filter).sort("created_at", -1):
        items.append(_serialize_quote(doc))

    return {"items": items, "status": st, "today": today_str}

@app.post("/api/requests/{quote_id}/confirm")
def admin_confirmar(quote_id: str, background: BackgroundTasks, user=Depends(require_api_key)):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = quotes.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    quotes.update_one({"_id": _id}, {"$set": {"estado": "confirmado", "confirmado_en": datetime.now(timezone.utc)}})
    
    # ✅ marcar booking como confirmado
    try:
        ft = doc.get("fecha_turno")
        ht = doc.get("hora_turno")
        if ft and ht:
            bookings.update_one(
                {"quote_id": str(_id), "date": ft, "time": ht},
                {"$set": {"status": "confirmed", "confirmed_at": datetime.now(timezone.utc)}},
                upsert=True
            )
    except Exception:
        pass

    doc = quotes.find_one({"_id": _id})
    background.add_task(_notify_confirmed_quote, doc)

    return {"message": "Presupuesto confirmado"}

@app.post("/api/requests/{quote_id}/complete")
def admin_completar(quote_id: str, user=Depends(require_api_key)):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    # Marcar quote como realizado
    updated = quotes.update_one(
        {"_id": _id},
        {"$set": {"estado": "realizado", "completed_at": datetime.now(timezone.utc)}}
    )
    if updated.matched_count == 0:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
        
    # Actualizar booking a completed (para que quede registro pero no bloquee igual que active?) 
    # En realidad completed sigue "ocupando" el slot histórico, está bien.
    bookings.update_many({"quote_id": quote_id}, {"$set": {"status": "completed"}})

    return {"message": "Trabajo completado"}

@app.post("/api/requests/{quote_id}/void")
def admin_anular(quote_id: str, user=Depends(require_api_key)):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    doc = quotes.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    # Marcar quote como anulado
    quotes.update_one(
        {"_id": _id},
        {"$set": {"estado": "anulado", "voided_at": datetime.now(timezone.utc)}}
    )

    # LIBERAR el slot del calendario (borrar booking)
    # Porque "Anulado" implica que el viaje no se hizo, entonces el slot "se liberó" (aunque sea en el pasado o futuro)
    bookings.delete_many({"quote_id": quote_id})
    
    # Si había override manual en availability, devolver el slot
    ft = doc.get("fecha_turno")
    ht = doc.get("hora_turno")
    if ft and ht:
        day_ovr = availability.find_one({"date": ft})
        if day_ovr and "slots" in day_ovr:
            availability.update_one(
                {"date": ft},
                {"$addToSet": {"slots": ht}}
            )

    return {"message": "Presupuesto anulado y horario liberado"}

@app.post("/api/requests/{quote_id}/reject")
def admin_rechazar(quote_id: str, user=Depends(require_api_key)):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    updated = quotes.update_one(
        {"_id": _id},
        {"$set": {"estado": "rechazado", "updated_at": datetime.utcnow()}}
    )

    if updated.matched_count == 0:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    return {"message": "Presupuesto rechazado"}

@app.delete("/api/requests/{quote_id}")
def admin_eliminar(quote_id: str, user=Depends(require_api_key)):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    doc = quotes.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    # ✅ recuperar turno antes de borrar
    ft = doc.get("fecha_turno")
    ht = doc.get("hora_turno")

    # ✅ borrar quote
    quotes.delete_one({"_id": _id})

    # ✅ Liberar horario
    if ft and ht:
        # 1) Borrar booking (esto ya libera el slot para los días "por defecto")
        bookings.delete_many({"quote_id": quote_id})
        bookings.delete_many({"date": ft, "time": ht})

        # 2) Devolver a 'availability' SOLO si el día ya tenía configuración custom
        # (Si el día no existe en 'availability', usa DEFAULT_SLOTS - bookings automáticamente)
        day_ovr = availability.find_one({"date": ft})
        if day_ovr and "slots" in day_ovr:
            availability.update_one(
                {"date": ft},
                {"$addToSet": {"slots": ht}, "$set": {"updated_at": datetime.now(timezone.utc)}}
            )

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
