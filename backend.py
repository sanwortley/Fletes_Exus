# backend.py
from datetime import datetime
import os
import uuid

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, DESCENDING
from bson.objectid import ObjectId

# ========================
# Config general
# ========================
app = FastAPI(title="Fletes Javier API")

# CORS (para poder abrir los .html directo en el navegador)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # en prod: poné tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["exus_fletes"]
quotes = db["quote_requests"]
quotes.create_index([("creado_en", DESCENDING)])

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
# Auxiliares
# ========================
def calcular_presupuesto(data: dict):
    """
    MVP: cálculo estimado sin Maps.
    (Luego podés reemplazar por Distance Matrix)
    """
    tipo_carga = (data.get("tipo_carga") or "mudanza").lower()
    tiempo_carga = float(data.get("tiempo_carga_descarga_min") or 0)

    base_km = 12 if tipo_carga == "mudanza" else 8
    # pequeño componente aleatorio para test
    dist_km = base_km + (uuid.uuid4().int % 8)
    tiempo_viaje_min = int(dist_km * 3.2 + tiempo_carga)
    monto_estimado = int(dist_km * 2200 + tiempo_viaje_min * 25)
    return dist_km, tiempo_viaje_min, monto_estimado

def to_public(x: dict):
    return {
        "id": str(x.get("_id")),
        "nombre_cliente": x.get("nombre_cliente"),
        "telefono": x.get("telefono"),
        "tipo_carga": x.get("tipo_carga"),
        "origen": x.get("origen"),
        "destino": x.get("destino"),
        "fecha": x.get("fecha"),
        "tiempo_carga_descarga_min": x.get("tiempo_carga_descarga_min"),
        "configuracion_camion": x.get("configuracion_camion"),
        "dist_km": x.get("dist_km"),
        "tiempo_viaje_min": x.get("tiempo_viaje_min"),
        "monto_estimado": x.get("monto_estimado"),
        "estado": x.get("estado"),
        "creado_en": x.get("creado_en"),
    }

def oid(qid: str) -> ObjectId:
    try:
        return ObjectId(qid)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

# ========================
# Endpoints públicos
# ========================
@app.get("/")
def root():
    return {"status": "ok", "db": "MongoDB", "service": "Fletes Javier API"}

@app.post("/api/quote")
def crear_presupuesto(payload: dict):
    nombre = (payload.get("nombre_cliente") or "").strip()
    telefono = (payload.get("telefono") or "").strip()
    if not nombre or not telefono:
        raise HTTPException(status_code=400, detail="Faltan datos obligatorios")

    dist_km, tiempo_viaje_min, monto_estimado = calcular_presupuesto(payload)

    doc = {
        "nombre_cliente": nombre,
        "telefono": telefono,
        "tipo_carga": payload.get("tipo_carga"),
        "origen": payload.get("origen"),
        "destino": payload.get("destino"),
        "fecha": payload.get("fecha"),
        "tiempo_carga_descarga_min": payload.get("tiempo_carga_descarga_min"),
        "configuracion_camion": payload.get("configuracion_camion", ""),
        "dist_km": dist_km,
        "tiempo_viaje_min": tiempo_viaje_min,
        "monto_estimado": monto_estimado,
        "estado": "pendiente",
        "creado_en": datetime.utcnow(),
    }
    res = quotes.insert_one(doc)
    doc["_id"] = res.inserted_id
    return {"ok": True, "quote": to_public(doc)}

# ========================
# Endpoints Admin (protegidos)
# ========================
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

# ========================
# Debug
# ========================
@app.get("/debug/dbinfo")
def dbinfo():
    total = quotes.count_documents({})
    one = quotes.find_one()
    return {
        "mongo_uri": MONGO_URI,
        "db": db.name,
        "collection": quotes.name,
        "count": total,
        "sample": (str(one["_id"]) if one else None),
    }
