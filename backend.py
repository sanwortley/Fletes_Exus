# ===================================
# 🚛 FLETES JAVIER – BACKEND COMPLETO (cálculo + admin + WhatsApp + email opcional)
# ===================================

from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt
import os
from typing import Optional, Dict, Any, List

import requests
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# Importá TU notifications.py (como ya lo tenés)
from notifications import send_whatsapp_to_javier  # usa Twilio con tus .env
# Si querés email, en notify_javier más abajo se usa SendGrid/SMTP si están en .env

# =========================
# Cargar variables de entorno
# =========================
load_dotenv()

# =========================
# App & CORS
# =========================
app = FastAPI(title="Fletes Javier API")
app.add_middleware(
    CORSMiddleware,
    # permito file:// (origen null) y live server por si lo usás
    allow_origins=["*", "null", "http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# MongoDB
# =========================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["fletes_db"]
quotes = db["quotes"]

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

# ===== estilo Excel / reglas =====
MANTENIMIENTO_PCT = float(os.getenv("MANTENIMIENTO_PCT", "0.20"))
COSTO_PEAJE = float(os.getenv("COSTO_PEAJE", "2000"))
COSTO_CHOFER_HORA = float(os.getenv("COSTO_CHOFER_HORA", "7500"))
COSTO_ADMIN_HORA = float(os.getenv("COSTO_ADMIN_HORA", "3500"))

REDONDEO_MIN = int(os.getenv("REDONDEO_MIN", "30"))          # 30' = 0.5 h
MIN_HORAS = float(os.getenv("MIN_HORAS", "2"))
BASE_FIJA = float(os.getenv("BASE_FIJA", "0"))
MIN_TOTAL = float(os.getenv("MIN_TOTAL", "0"))
INCLUIR_AYUDANTE_EN_TOTAL = (os.getenv("INCLUIR_AYUDANTE_EN_TOTAL", "1") == "1")

# Vuelta a base por defecto si el front no manda bandera
RETURN_TO_BASE_DEFAULT = (os.getenv("RETURN_TO_BASE_DEFAULT", "0") == "1")

# =========================
# Notificaciones (env) - opcional email
# =========================
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO_JAVIER = os.getenv("EMAIL_TO_JAVIER")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# =========================
# Admin (env)
# =========================
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# =========================
# Modelos
# =========================
class QuoteIn(BaseModel):
    nombre_cliente: str
    telefono: str
    tipo_carga: str
    origen: str
    destino: str
    fecha: Optional[str] = None
    ayudante: bool = False

    # Trayecto
    regreso_base: Optional[bool] = None  # si None, usa RETURN_TO_BASE_DEFAULT

    # Horas reales (opcional)
    hora_inicio: Optional[str] = None   # "HH:MM" o "YYYY-MM-DD HH:MM"
    hora_fin: Optional[str] = None
    horas_reales: Optional[float] = None

    # Extras
    peajes: int = 0
    viaticos: float = 0.0

    # consentimiento
    accepted_terms: bool = Field(False, description="Cliente aceptó condiciones")
    accepted_terms_at: Optional[datetime] = Field(None, description="Fecha/hora ISO aceptación")


class QuoteOut(QuoteIn):
    id: str
    dist_km: float = 0
    tiempo_viaje_min: int = 0
    tiempo_servicio_min: int = 0
    horas_base: float = 0
    costo_tiempo_base: float = 0
    mantenimiento: float = 0
    costo_tiempo: float = 0
    costo_combustible: float = 0
    peajes_total: float = 0
    costo_ayudante: float = 0
    costo_chofer_parcial: float = 0
    costo_admin_parcial: float = 0
    monto_estimado: float = 0
    estado: str = "pendiente"

    # detalle de tramos
    tramo_base_origen_km: float = 0
    tramo_origen_destino_km: float = 0
    tramo_destino_base_km: float = 0
    tramo_base_origen_min: int = 0
    tramo_origen_destino_min: int = 0
    tramo_destino_base_min: int = 0


class ConfirmPayload(BaseModel):
    fecha_hora_preferida: Optional[str] = None
    notas: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    role: str = "admin"


class EstadoPayload(BaseModel):
    estado: str = Field(description="pendiente | confirmado | cancelado | realizado")

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
    """Si la dirección no trae ciudad/provincia, le agrega DEFAULT_LOCALITY."""
    s = (s or "").strip()
    if not s:
        return DEFAULT_LOCALITY
    loc = DEFAULT_LOCALITY.lower()
    if loc not in s.lower():
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
        js = requests.get(r_url, headers=hdr,
                          params={"start": f"{o[1]},{o[0]}", "end": f"{d[1]},{d[0]}"}, timeout=12).json()
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
        dist_km = 10.0  # base heurística
    tiempo_viaje_min = int(round((dist_km / max(VEL_KMH, 1)) * 60))
    return {"dist_km": round(dist_km, 2), "tiempo_viaje_min": int(tiempo_viaje_min)}


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


def calcular_costos(
    dist_km: float, tiempo_viaje_min: int, ayudante: bool,
    horas_reales: Optional[float] = None, peajes: int = 0, viaticos: float = 0.0
) -> Dict[str, float]:
    horas_manejo = tiempo_viaje_min / 60.0
    horas_servicio = horas_manejo * FACTOR_PONDERACION
    horas_base = horas_reales if (horas_reales and horas_reales > 0) else (horas_manejo + horas_servicio)

    # redondeo + mínimo
    if REDONDEO_MIN > 0:
        bloque_h = REDONDEO_MIN / 60.0
        import math
        horas_base = bloque_h * math.ceil(horas_base / bloque_h)
    horas_base = max(horas_base, MIN_HORAS)

    # costos
    costo_tiempo_base = horas_base * COSTO_HORA
    mantenimiento = costo_tiempo_base * MANTENIMIENTO_PCT
    costo_tiempo_total = costo_tiempo_base + mantenimiento

    costo_combustible = (dist_km / max(KM_POR_LITRO, 0.1)) * COSTO_LITRO
    peajes_total = peajes * COSTO_PEAJE
    costo_ayudante = horas_base * COSTO_HORA_AYUDANTE if ayudante else 0.0
    costo_chofer_parcial = horas_base * COSTO_CHOFER_HORA
    costo_admin_parcial = horas_base * COSTO_ADMIN_HORA

    monto_estimado = BASE_FIJA + costo_tiempo_total + costo_combustible + peajes_total + viaticos
    if INCLUIR_AYUDANTE_EN_TOTAL:
        monto_estimado += costo_ayudante
    monto_estimado = max(monto_estimado, MIN_TOTAL)

    return {
        "horas_base": round(horas_base, 2),
        "tiempo_servicio_min": int(round(horas_servicio * 60)),
        "costo_tiempo_base": round(costo_tiempo_base, 2),
        "mantenimiento": round(mantenimiento, 2),
        "costo_tiempo": round(costo_tiempo_total, 2),
        "costo_combustible": round(costo_combustible, 2),
        "peajes_total": round(peajes_total, 2),
        "viaticos": round(viaticos, 2),
        "costo_ayudante": round(costo_ayudante, 2),
        "costo_chofer_parcial": round(costo_chofer_parcial, 2),
        "costo_admin_parcial": round(costo_admin_parcial, 2),
        "monto_estimado": round(monto_estimado, 2),
    }

# =========================
# Email opcional
# =========================
def send_email_sendgrid(subject: str, html: str) -> Optional[str]:
    if not all([SENDGRID_API_KEY, EMAIL_FROM, EMAIL_TO_JAVIER]):
        return "SendGrid env vars faltantes"
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        resp = SendGridAPIClient(SENDGRID_API_KEY).send(
            Mail(from_email=EMAIL_FROM, to_emails=EMAIL_TO_JAVIER, subject=subject, html_content=html)
        )
        return f"sendgrid_status={resp.status_code}"
    except Exception as e:
        return f"sendgrid_error:{e}"


def send_email_smtp(subject: str, html: str) -> Optional[str]:
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, EMAIL_TO_JAVIER]):
        return "SMTP env vars faltantes"
    try:
        import smtplib, ssl
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject; msg["From"] = EMAIL_FROM; msg["To"] = EMAIL_TO_JAVIER
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(EMAIL_FROM, [EMAIL_TO_JAVIER], msg.as_string())
        return "smtp_ok"
    except Exception as e:
        return f"smtp_error:{e}"


def notify_javier(subject: str, text: str, html: str) -> Dict[str, str]:
    # WhatsApp (no frena el flujo si falla)
    wp = send_whatsapp_to_javier(text) or ""
    # Email opcional (SendGrid si hay API_KEY, si no SMTP)
    if SENDGRID_API_KEY:
        em = send_email_sendgrid(subject, html) or ""
    else:
        em = send_email_smtp(subject, html) or ""
    return {"whatsapp": wp, "email": em}

# =========================
# Rutas core
# =========================
@app.get("/")
def health():
    return {"status": "ok", "service": "Fletes Javier API"}


@app.post("/api/quote")
def crear_quote(body: QuoteIn):
    accepted_at = body.accepted_terms_at or (datetime.now(timezone.utc) if body.accepted_terms else None)

    # 1) Normalizar direcciones
    origen_norm = _normalize_addr(body.origen)
    destino_norm = _normalize_addr(body.destino)
    base_norm = _normalize_addr(BASE_DIRECCION)

    # 2) Calcular tramos: BASE→ORIGEN y ORIGEN→DESTINO (y opcional DESTINO→BASE)
    t1 = calcular_ruta(base_norm, origen_norm)       # base -> origen
    t2 = calcular_ruta(origen_norm, destino_norm)    # origen -> destino

    dist_total = float(t1["dist_km"] + t2["dist_km"])
    tiempo_total_min = int(t1["tiempo_viaje_min"] + t2["tiempo_viaje_min"])

    # 3) Vuelta a base (opcional)
    regreso_flag = body.regreso_base if body.regreso_base is not None else RETURN_TO_BASE_DEFAULT
    t3 = {"dist_km": 0.0, "tiempo_viaje_min": 0}
    if regreso_flag:
        t3 = calcular_ruta(destino_norm, base_norm)  # destino -> base
        dist_total += float(t3["dist_km"])
        tiempo_total_min += int(t3["tiempo_viaje_min"])

    # 4) Horas reales (prioridad: horas_reales > inicio/fin)
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

    # 5) Costos
    costos = calcular_costos(
        dist_total, tiempo_total_min, body.ayudante,
        horas_reales=horas_reales, peajes=body.peajes, viaticos=body.viaticos
    )

    # 6) Persistir
    doc = {
        "nombre_cliente": body.nombre_cliente, "telefono": body.telefono, "tipo_carga": body.tipo_carga,
        "origen": body.origen, "destino": body.destino, "fecha": body.fecha, "ayudante": body.ayudante,
        "regreso_base": regreso_flag,
        "hora_inicio": body.hora_inicio, "hora_fin": body.hora_fin, "horas_reales": horas_reales,
        "peajes": body.peajes, "viaticos": body.viaticos,
        "accepted_terms": body.accepted_terms, "accepted_terms_at": accepted_at,

        # totales
        "dist_km": round(dist_total, 3), "tiempo_viaje_min": int(tiempo_total_min),
        "tiempo_servicio_min": costos["tiempo_servicio_min"],
        "horas_base": costos["horas_base"],

        # desgloses
        "costo_tiempo_base": costos["costo_tiempo_base"], "mantenimiento": costos["mantenimiento"],
        "costo_tiempo": costos["costo_tiempo"], "costo_combustible": costos["costo_combustible"],
        "peajes_total": costos["peajes_total"], "costo_ayudante": costos["costo_ayudante"],
        "costo_chofer_parcial": costos["costo_chofer_parcial"], "costo_admin_parcial": costos["costo_admin_parcial"],
        "monto_estimado": costos["monto_estimado"],

        # tramos
        "tramo_base_origen_km": round(t1["dist_km"], 3),
        "tramo_origen_destino_km": round(t2["dist_km"], 3),
        "tramo_destino_base_km": round(t3["dist_km"], 3),
        "tramo_base_origen_min": int(t1["tiempo_viaje_min"]),
        "tramo_origen_destino_min": int(t2["tiempo_viaje_min"]),
        "tramo_destino_base_min": int(t3["tiempo_viaje_min"]),

        "estado": "pendiente", "created_at": datetime.now(timezone.utc),
    }
    doc["_id"] = quotes.insert_one(doc).inserted_id

    # 7) Notificación SOLO de aviso (Javier entra al admin a confirmar)
    try:
        msg = (
            "🚛 *Nuevo pedido de presupuesto*\n\n"
            f"👤 {doc['nombre_cliente']}  \n 📞 {doc['telefono']}\n"
            f"📍 {doc['origen']}  →  🏁 {doc['destino']}\n"
            f"🧮 Estimado: $ {int(doc['monto_estimado']):,}".replace(",", ".")
        )
        send_whatsapp_to_javier(msg)
    except Exception:
        pass

    out = QuoteOut(id=str(doc["_id"]), **{k: doc[k] for k in doc if k not in {"_id", "created_at"}})
    return {"quote": out.model_dump()}  # si usás Pydantic v1, usá .dict()

# ===== Compat: confirmación “clásica” por /api/quotes/{id}/confirm =====
@app.post("/api/quotes/{quote_id}/confirm")
def confirmar_quote(quote_id: str, body: ConfirmPayload = Body(default=None)):
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
            "fecha_hora_preferida": body.fecha_hora_preferida if body else None,
            "notas_confirmacion": body.notas if body else None
        }})
        doc = quotes.find_one({"_id": _id})

    subject = "Presupuesto CONFIRMADO"
    text = (
        "✅ PRESUPUESTO CONFIRMADO\n\n"
        f"Cliente: {doc.get('nombre_cliente')} ({doc.get('telefono')})\n"
        f"Tipo: {doc.get('tipo_carga')}\n"
        f"Origen → Destino: {doc.get('origen')} → {doc.get('destino')}\n"
        f"Fecha solicitada: {doc.get('fecha') or '-'}\n"
        f"Ayudante: {'Sí' if doc.get('ayudante') else 'No'}\n"
        f"Distancia total: {doc.get('dist_km',0)} km | Viaje: {doc.get('tiempo_viaje_min',0)} min\n"
        f"Total: $ {int(doc.get('monto_estimado',0)):,}".replace(",", ".") + "\n"
        f"ID: {str(doc.get('_id'))}\n"
    )
    html = f"""
    <h2>Presupuesto CONFIRMADO</h2>
    <p><b>Cliente:</b> {doc.get('nombre_cliente')} ({doc.get('telefono')})</p>
    <p><b>Tipo:</b> {doc.get('tipo_carga')}</p>
    <p><b>Origen → Destino:</b> {doc.get('origen')} → {doc.get('destino')}</p>
    <p><b>Fecha solicitada:</b> {doc.get('fecha') or '-'}</p>
    <p><b>Ayudante:</b> {"Sí" if doc.get('ayudante') else "No"}</p>
    <p><b>Distancia total:</b> {doc.get('dist_km',0)} km — <b>Viaje:</b> {doc.get('tiempo_viaje_min',0)} min</p>
    <p><b>Total:</b> $ {int(doc.get('monto_estimado',0)):,}</p>
    <p><b>ID:</b> {str(doc.get('_id'))}</p>
    <hr/><small>Exus Fletes</small>
    """
    _ = notify_javier(subject, text, html)  # email opcional
    return {"message": "Confirmado"}


@app.post("/api/test-notify")
def test_notify():
    subject = "Test Notificación – Exus Fletes"
    text = "🔔 Test de notificación WhatsApp desde Exus Fletes"
    html = "<h3>Test Email OK</h3><p>Este es un envío de prueba.</p>"
    return {"ok": True, "notifications": notify_javier(subject, text, html)}

# =========================
# Rutas Admin para admin.html
# =========================
def _serialize_quote(doc: dict) -> dict:
    # Incluyo TODO lo que el modal puede mostrar
    return {
        "id": str(doc.get("_id")),
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

        "costo_tiempo_base": float(doc.get("costo_tiempo_base", 0)),
        "mantenimiento": float(doc.get("mantenimiento", 0)),
        "costo_tiempo": float(doc.get("costo_tiempo", 0)),
        "costo_combustible": float(doc.get("costo_combustible", 0)),
        "costo_ayudante": float(doc.get("costo_ayudante", 0)),
        "peajes_total": float(doc.get("peajes_total", 0)),
        "monto_estimado": float(doc.get("monto_estimado", 0)),

        "tramo_base_origen_km": float(doc.get("tramo_base_origen_km", 0)),
        "tramo_origen_destino_km": float(doc.get("tramo_origen_destino_km", 0)),
        "tramo_destino_base_km": float(doc.get("tramo_destino_base_km", 0)),
        "tramo_base_origen_min": int(doc.get("tramo_base_origen_min", 0)),
        "tramo_origen_destino_min": int(doc.get("tramo_origen_destino_min", 0)),
        "tramo_destino_base_min": int(doc.get("tramo_destino_base_min", 0)),

        "estado": doc.get("estado", "pendiente"),
        "created_at": (doc.get("created_at") or datetime.now(timezone.utc)).isoformat(),
    }


@app.post("/api/login", response_model=LoginOut)
def admin_login(body: LoginIn):
    if body.username == ADMIN_USER and body.password == ADMIN_PASS:
        return LoginOut(token="dummy-admin-token", role="admin")
    raise HTTPException(status_code=401, detail="Credenciales inválidas")


@app.get("/api/requests")
def listar_requests():
    items: List[dict] = []
    for doc in quotes.find().sort("created_at", -1):
        items.append(_serialize_quote(doc))
    return {"items": items}


# Endpoints “por acción” para el admin.html
@app.post("/api/requests/{quote_id}/confirm")
def admin_confirmar(quote_id: str):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = quotes.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    quotes.update_one({"_id": _id}, {"$set": {"estado": "confirmado", "confirmado_en": datetime.now(timezone.utc)}})

    # Aviso por WhatsApp (y opcional mail)
    text = (
        "✅ *Presupuesto confirmado*\n\n"
        f"Cliente: {doc.get('nombre_cliente')} ({doc.get('telefono')})\n"
        f"Origen → Destino: {doc.get('origen')} → {doc.get('destino')}\n"
        f"Total: $ {int(doc.get('monto_estimado',0)):,}".replace(",", ".")
    )
    try:
        send_whatsapp_to_javier(text)
    except Exception:
        pass
    return {"message": "Presupuesto confirmado"}


@app.post("/api/requests/{quote_id}/reject")
def admin_rechazar(quote_id: str):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if quotes.update_one({"_id": _id}, {"$set": {"estado": "rechazado"}}).matched_count == 0:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    return {"message": "Presupuesto rechazado"}


@app.delete("/api/requests/{quote_id}")
def admin_eliminar(quote_id: str):
    try:
        _id = ObjectId(quote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = quotes.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    if (doc.get("estado") or "").lower() != "rechazado":
        raise HTTPException(status_code=400, detail="Solo se puede eliminar si está Rechazado")
    quotes.delete_one({"_id": _id})
    return {"message": "Eliminado"}

# =========================
# Runner local
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="127.0.0.1", port=8000, reload=True)
