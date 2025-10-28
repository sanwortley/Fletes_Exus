# backend.py
from datetime import datetime
import os
import uuid

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, DESCENDING
from bson import ObjectId
from dotenv import load_dotenv

import openrouteservice

load_dotenv()

# ========================
# Config general
# ========================
app = FastAPI(title="Fletes Javier API")

# CORS (abrir HTML directamente en navegador)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod: poner dominio
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
# ORS (OpenRouteService)
# ========================
ORS_API_KEY = os.getenv("ORS_API_KEY")
if not ORS_API_KEY:
    print("⚠️ ORS_API_KEY no definido: /api/quote usará circuito si está presente.")
ors_client = openrouteservice.Client(key=ORS_API_KEY) if ORS_API_KEY else None

BASE_DIRECCION = os.getenv("BASE_DIRECCION", "Pasaje Liñán 1941, Córdoba, Argentina")
KM_POR_LITRO = float(os.getenv("KM_POR_LITRO", 8))
COSTO_LITRO = float(os.getenv("COSTO_LITRO", 1600))
COSTO_HORA = float(os.getenv("COSTO_HORA", 25000))
COSTO_HORA_AYUDANTE = float(os.getenv("COSTO_HORA_AYUDANTE", 10000))
FACTOR_PONDERACION = float(os.getenv("FACTOR_PONDERACION", 1.5))

# ========================
# Sesiones/Login simple
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
# Utilidades
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

def geocode_ors(texto: str):
    if not ors_client:
        raise HTTPException(status_code=500, detail="ORS_API_KEY no configurada")
    res = ors_client.pelias_search(text=texto)
    if not res.get("features"):
        raise HTTPException(status_code=400, detail=f"No se pudo geocodificar: {texto}")
    return res["features"][0]["geometry"]["coordinates"]  # [lon, lat]

def calcular_circuito_dist_y_tiempo(origen: str, destino: str):
    """
    Ruta real: base → origen → destino → base
    """
    if not ors_client:
        raise HTTPException(status_code=500, detail="ORS_API_KEY no configurada")
    try:
        base = geocode_ors(BASE_DIRECCION)
        a = geocode_ors(origen)
        b = geocode_ors(destino)
        route = ors_client.directions(
            coordinates=[base, a, b, base],
            profile="driving-car",
            format="geojson",
        )
        props = route["features"][0]["properties"]["summary"]
        distancia_km = round(props["distance"] / 1000, 2)
        tiempo_min = round(props["duration"] / 60, 1)  # manejo puro
        return distancia_km, tiempo_min
    except HTTPException:
        raise
    except Exception as e:
        print("Error calcular_circuito_dist_y_tiempo:", e)
        raise HTTPException(status_code=500, detail="Error calculando circuito")

def calcular_costo_total(tipo_carga: str, dist_km: float, tiempo_manejo_min: float, ayudante: bool):
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
    """
    Devuelve distancia/tiempo manejo entre origen y destino directos (sin circuito).
    """
    if not ors_client:
        raise HTTPException(status_code=500, detail="ORS_API_KEY no configurada")
    origen = (payload.get("origen") or "").strip()
    destino = (payload.get("destino") or "").strip()
    if not origen or not destino:
        raise HTTPException(status_code=400, detail="Faltan direcciones")

    try:
        a = geocode_ors(origen)
        b = geocode_ors(destino)
        route = ors_client.directions(
            coordinates=[a, b],
            profile="driving-car",
            format="geojson",
        )
        props = route["features"][0]["properties"]["summary"]
        return {
            "dist_km": round(props["distance"] / 1000, 2),
            "tiempo_min": round(props["duration"] / 60, 1),
        }
    except HTTPException:
        raise
    except Exception as e:
        print("Error /api/distancia:", e)
        raise HTTPException(status_code=500, detail="No se pudo calcular la distancia")

@app.post("/api/quote")
def crear_presupuesto(payload: dict):
    """
    Calcula:
    - Circuito base→origen→destino→base (ORS)
    - Tiempo servicio = manejo*1.5 + (1h mudanza / 0.5h no mudanza)
    - Combustible, tiempo y ayudante (si aplica)
    """
    nombre = (payload.get("nombre_cliente") or "").strip()
    telefono = (payload.get("telefono") or "").strip()
    if not nombre or not telefono:
        raise HTTPException(status_code=400, detail="Faltan datos obligatorios")

    tipo_carga = (payload.get("tipo_carga") or "mudanza").lower()
    origen = (payload.get("origen") or "").strip()
    destino = (payload.get("destino") or "").strip()
    fecha = payload.get("fecha")  # string opcional
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
        "creado_en": datetime.utcnow(),
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
    """
    Eliminar SOLO si está 'rechazado'
    """
    doc = quotes.find_one({"_id": oid(qid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Request not found")
    if doc.get("estado") != "rechazado":
        raise HTTPException(status_code=400, detail="Solo se puede eliminar si está rechazado")
    quotes.delete_one({"_id": doc["_id"]})
    return {"ok": True}
