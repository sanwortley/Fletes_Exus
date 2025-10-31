# backend.py
from datetime import datetime as dt
import os
import uuid
from math import radians, sin, cos, asin, sqrt

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, DESCENDING
from bson import ObjectId
from dotenv import load_dotenv

import requests
import openrouteservice
import googlemaps

load_dotenv()

# ========================
# Config general
# ========================
app = FastAPI(title="Fletes Javier API")

# CORS (para servir front local o file:// durante dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # en prod: poner tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================
# MongoDB
# ========================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["exus_fletes"]
quotes = db["quote_requests"]
quotes.create_index([("creado_en", DESCENDING)])

# ========================
# Servicios externos / Parámetros
# ========================
ROUTING_PROVIDER = os.getenv("ROUTING_PROVIDER", "ors").lower()

# ORS
ORS_API_KEY = os.getenv("ORS_API_KEY")
ors_client = openrouteservice.Client(key=ORS_API_KEY) if ORS_API_KEY else None

# Google
GMAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GMAPS_REGION = os.getenv("MAPS_REGION", "AR")
GMAPS_LANGUAGE = os.getenv("MAPS_LANGUAGE", "es")
gmaps = googlemaps.Client(key=GMAPS_KEY) if (GMAPS_KEY and ROUTING_PROVIDER == "google") else None

BASE_DIRECCION = os.getenv("BASE_DIRECCION", "Pasaje Liñán 1941, Córdoba, Argentina")

# Cálculo de costos
KM_POR_LITRO = float(os.getenv("KM_POR_LITRO", 8))
COSTO_LITRO = float(os.getenv("COSTO_LITRO", 2000))  # ajustalo si la nafta sube
COSTO_HORA = float(os.getenv("COSTO_HORA", 25000))
COSTO_HORA_AYUDANTE = float(os.getenv("COSTO_HORA_AYUDANTE", 10000))
FACTOR_PONDERACION = float(os.getenv("FACTOR_PONDERACION", 1.5))  # manejo * 1.5

# Fallback/ruteo sin key
DEFAULT_LOCALITY = os.getenv("DEFAULT_LOCALITY", "Córdoba, Argentina")
FACTOR_TRAZADO = float(os.getenv("FACTOR_TRAZADO", 1.25))  # sinuocidad vs. línea recta
VEL_KMH = float(os.getenv("VEL_KMH", 35))                   # velocidad media urbana

# ========================
# Sesiones/login simple
# ========================
SESSIONS: set[str] = set()
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

def require_auth(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth.split(" ", 1)[1].strip()
    if token not in SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/api/login")
def login(payload: dict):
    username = payload.get("username", "")
    password = payload.get("password", "")
    if username == ADMIN_USER and password == ADMIN_PASS:
        tok = uuid.uuid4().hex
        SESSIONS.add(tok)
        return {"ok": True, "token": tok}
    raise HTTPException(status_code=401, detail="Invalid credentials")

# ========================
# Utils
# ========================
def oid(qid: str) -> ObjectId:
    try:
        return ObjectId(qid)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

def to_public(x: dict):
    return {
        "id": str(x.get("_id")),
        "nombre_cliente": x.get("nombre_cliente"),
        "telefono": x.get("telefono"),
        "tipo_carga": x.get("tipo_carga"),
        "origen": x.get("origen"),
        "destino": x.get("destino"),
        "fecha": x.get("fecha"),
        "ayudante": x.get("ayudante", False),
        "tiempo_carga_descarga_min": x.get("tiempo_carga_descarga_min"),
        "dist_km": x.get("dist_km"),
        "tiempo_viaje_min": x.get("tiempo_viaje_min"),
        "tiempo_servicio_min": x.get("tiempo_servicio_min"),
        "costo_tiempo": x.get("costo_tiempo"),
        "costo_combustible": x.get("costo_combustible"),
        "costo_ayudante": x.get("costo_ayudante"),
        "monto_estimado": x.get("monto_estimado"),
        "estado": x.get("estado"),
        "creado_en": x.get("creado_en"),
    }

def normalize_addr(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    low = s.lower()
    if "cordoba" not in low and "córdoba" not in low and "argentina" not in low:
        s = f"{s}, {DEFAULT_LOCALITY}"
    return s

# ========================
# Geocoding (Google / ORS / Nominatim)
# ========================
def geocode_google(texto: str):
    if not gmaps:
        raise HTTPException(status_code=500, detail="GOOGLE_MAPS_API_KEY no configurada o ROUTING_PROVIDER != google")
    res = gmaps.geocode(texto, region=GMAPS_REGION, language=GMAPS_LANGUAGE)
    if not res:
        raise HTTPException(status_code=400, detail=f"No se pudo geocodificar: {texto}")
    loc = res[0]["geometry"]["location"]
    return [loc["lng"], loc["lat"]]  # [lon, lat]

def geocode_nominatim(texto: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": texto, "format": "json", "limit": 1}
    headers = {"User-Agent": "FletesJavier/1.0 (contacto: admin@example.com)"}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise HTTPException(status_code=400, detail=f"No se pudo geocodificar: {texto}")
    return [float(data[0]["lon"]), float(data[0]["lat"])]

def geocode_any(texto: str):
    texto = normalize_addr(texto)
    # 1) Google (si está activo)
    if ROUTING_PROVIDER == "google" and gmaps:
        try:
            return geocode_google(texto)
        except Exception:
            pass
    # 2) ORS (si hay key)
    if ors_client:
        try:
            res = ors_client.pelias_search(text=texto)
            if res.get("features"):
                return res["features"][0]["geometry"]["coordinates"]  # [lon, lat]
        except Exception:
            pass
    # 3) Nominatim
    return geocode_nominatim(texto)

# ========================
# Routing helpers (Google / ORS / OSRM / Haversine)
# ========================
def directions_google(coords):
    """
    coords: lista [[lon,lat], ...]
    Soporta circuitos con waypoints: BASE→A→B→BASE.
    """
    if not gmaps:
        raise HTTPException(status_code=500, detail="GOOGLE_MAPS_API_KEY no configurada o ROUTING_PROVIDER != google")
    if len(coords) < 2:
        raise HTTPException(status_code=400, detail="Se requieren al menos 2 puntos")

    def to_str(lon, lat): return f"{lat},{lon}"
    origin = to_str(*coords[0])
    destination = to_str(*coords[-1])
    waypoints = [to_str(*c) for c in coords[1:-1]] if len(coords) > 2 else None

    route = gmaps.directions(
        origin=origin,
        destination=destination,
        waypoints=waypoints,
        mode="driving",
        language=GMAPS_LANGUAGE,
        region=GMAPS_REGION,
        departure_time=dt.now()
    )
    if not route:
        raise HTTPException(status_code=500, detail="Google Directions no devolvió ruta")

    legs = route[0]["legs"]
    dist_m = sum(leg["distance"]["value"] for leg in legs)
    dur_s  = sum(leg["duration"]["value"] for leg in legs)
    return round(dist_m/1000, 2), round(dur_s/60, 1)

def osrm_route(coords):
    """
    coords: lista [(lon,lat), ...] (≥2 puntos)
    """
    base_url = "https://router.project-osrm.org/route/v1/driving/"
    path = ";".join([f"{lon},{lat}" for lon, lat in coords])
    params = {"overview": "false", "alternatives": "false", "steps": "false"}
    r = requests.get(base_url + path, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok":
        raise RuntimeError("OSRM devolvió código no OK")
    route = data["routes"][0]
    dist_km = round(route["distance"] / 1000, 2)
    dur_min = round(route["duration"] / 60, 1)
    return dist_km, dur_min

def haversine_km(lon1, lat1, lon2, lat2):
    R = 6371.0
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def calcular_circuito_dist_y_tiempo(origen: str, destino: str):
    """
    Circuito real: base → origen → destino → base
    Orden: Google → ORS → OSRM → Haversine
    """
    try:
        base = geocode_any(BASE_DIRECCION)
        a = geocode_any(origen)
        b = geocode_any(destino)
    except HTTPException:
        raise
    except Exception as e:
        print("Error geocoding:", e)
        raise HTTPException(status_code=500, detail="Error geocodificando direcciones")

    # 1) Google
    if ROUTING_PROVIDER == "google" and gmaps:
        try:
            return directions_google([base, a, b, base])
        except Exception as e:
            print("Google routing fallback:", e)

    # 2) ORS
    if ors_client:
        try:
            route = ors_client.directions(
                coordinates=[base, a, b, base],
                profile="driving-car",
                format="geojson",
            )
            props = route["features"][0]["properties"]["summary"]
            return round(props["distance"]/1000, 2), round(props["duration"]/60, 1)
        except Exception as e:
            print("ORS routing fallback:", e)

    # 3) OSRM
    try:
        return osrm_route([base, a, b, base])
    except Exception as e:
        print("OSRM fallback:", e)

    # 4) Haversine
    try:
        segs = [(base, a), (a, b), (b, base)]
        total_km = 0.0
        for (lonlat1, lonlat2) in segs:
            lon1, lat1 = lonlat1
            lon2, lat2 = lonlat2
            total_km += haversine_km(lon1, lat1, lon2, lat2)
        distancia_km = round(total_km * FACTOR_TRAZADO, 2)
        tiempo_min = round((distancia_km / VEL_KMH) * 60, 1)
        return distancia_km, tiempo_min
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo estimar el circuito")

# ========================
# Costos
# ========================
def calcular_costo_total(tipo_carga: str, dist_km: float, tiempo_manejo_min: float, ayudante: bool):
    # tiempo manejo real → ponderado + carga/descarga
    tiempo_h = tiempo_manejo_min / 60.0
    extra_h = 1.0 if (tipo_carga or "").lower() == "mudanza" else 0.5
    tiempo_servicio_h = tiempo_h * FACTOR_PONDERACION + extra_h

    costo_tiempo = tiempo_servicio_h * COSTO_HORA
    costo_combustible = (dist_km / KM_POR_LITRO) * COSTO_LITRO
    costo_ayudante = tiempo_servicio_h * COSTO_HORA_AYUDANTE if ayudante else 0.0
    total = costo_tiempo + costo_combustible + costo_ayudante

    return {
        "tiempo_servicio_min": round(tiempo_servicio_h * 60, 0),
        "costo_tiempo": round(costo_tiempo),
        "costo_combustible": round(costo_combustible),
        "costo_ayudante": round(costo_ayudante),
        "total": round(total),
    }

# ========================
# Endpoints
# ========================
@app.get("/")
def root():
    return {"status": "ok", "service": "Fletes Javier API"}

@app.post("/api/distancia")
def obtener_distancia(payload: dict):
    """Distancia/tiempo entre origen y destino directos (con fallbacks)."""
    origen = normalize_addr(payload.get("origen", ""))
    destino = normalize_addr(payload.get("destino", ""))
    if not origen or not destino:
        raise HTTPException(status_code=400, detail="Faltan direcciones")

    a = geocode_any(origen)
    b = geocode_any(destino)

    # 1) Google
    if ROUTING_PROVIDER == "google" and gmaps:
        try:
            dk, tm = directions_google([a, b])
            return {"dist_km": dk, "tiempo_min": tm}
        except Exception as e:
            print("Google /api/distancia fallback:", e)

    # 2) ORS directo
    if ors_client:
        try:
            route = ors_client.directions(
                coordinates=[a, b], profile="driving-car", format="geojson"
            )
            props = route["features"][0]["properties"]["summary"]
            return {
                "dist_km": round(props["distance"]/1000, 2),
                "tiempo_min": round(props["duration"]/60, 1),
            }
        except Exception as e:
            print("ORS /api/distancia fallback:", e)

    # 3) OSRM
    try:
        dk, tm = osrm_route([a, b])
        return {"dist_km": dk, "tiempo_min": tm}
    except Exception as e:
        print("OSRM /api/distancia fallback:", e)

    # 4) Haversine
    dist_km = round(haversine_km(a[0], a[1], b[0], b[1]) * FACTOR_TRAZADO, 2)
    tiempo_min = round((dist_km / VEL_KMH) * 60, 1)
    return {"dist_km": dist_km, "tiempo_min": tiempo_min}

@app.post("/api/quote")
def crear_presupuesto(payload: dict):
    """
    Calcula:
    - Circuito base→origen→destino→base (Google/ORS/OSRM/Haversine)
    - Tiempo servicio = manejo*1.5 + (1h mudanza / 0.5h no mudanza)
    - Costos de tiempo, combustible y ayudante
    """
    nombre = (payload.get("nombre_cliente") or "").strip()
    telefono = (payload.get("telefono") or "").strip()
    if not nombre or not telefono:
        raise HTTPException(status_code=400, detail="Faltan datos obligatorios")

    tipo_carga = (payload.get("tipo_carga") or "mudanza").lower()
    origen = (payload.get("origen") or "").strip()
    destino = (payload.get("destino") or "").strip()
    fecha = payload.get("fecha")
    ayudante = bool(payload.get("ayudante", False))

    if not origen or not destino:
        raise HTTPException(status_code=400, detail="Falta origen/destino")

    dist_km, tiempo_manejo_min = calcular_circuito_dist_y_tiempo(origen, destino)
    costos = calcular_costo_total(tipo_carga, dist_km, tiempo_manejo_min, ayudante)

    doc = {
        "nombre_cliente": nombre,
        "telefono": telefono,
        "tipo_carga": tipo_carga,
        "origen": origen,
        "destino": destino,
        "fecha": fecha,
        "ayudante": ayudante,
        "tiempo_carga_descarga_min": 60 if tipo_carga == "mudanza" else 30,
        "dist_km": dist_km,
        "tiempo_viaje_min": tiempo_manejo_min,
        "tiempo_servicio_min": costos["tiempo_servicio_min"],
        "costo_tiempo": costos["costo_tiempo"],
        "costo_combustible": costos["costo_combustible"],
        "costo_ayudante": costos["costo_ayudante"],
        "monto_estimado": costos["total"],
        "estado": "pendiente",
        "creado_en": dt.utcnow(),
    }
    res = quotes.insert_one(doc)
    doc["_id"] = res.inserted_id
    return {"ok": True, "quote": to_public(doc)}

# --------- ADMIN (protegidos) ----------
@app.get("/api/requests", dependencies=[Depends(require_auth)])
def listar_solicitudes():
    cursor = quotes.find({}).sort("creado_en", DESCENDING)
    return {"items": [to_public(x) for x in cursor]}

@app.post("/api/requests/{qid}/confirm", dependencies=[Depends(require_auth)])
def confirmar(qid: str):
    result = quotes.update_one({"_id": oid(qid)}, {"$set": {"estado": "confirmado"}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"ok": True}

@app.post("/api/requests/{qid}/reject", dependencies=[Depends(require_auth)])
def rechazar(qid: str):
    result = quotes.update_one({"_id": oid(qid)}, {"$set": {"estado": "rechazado"}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"ok": True}

@app.delete("/api/requests/{qid}", dependencies=[Depends(require_auth)])
def eliminar(qid: str):
    doc = quotes.find_one({"_id": oid(qid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Request not found")
    if (doc.get("estado") or "").lower() != "rechazado":
        raise HTTPException(status_code=400, detail="Solo se puede eliminar si está rechazado")
    quotes.delete_one({"_id": doc["_id"]})
    return {"ok": True}
