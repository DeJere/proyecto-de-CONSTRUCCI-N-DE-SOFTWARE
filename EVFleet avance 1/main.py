import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import requests
from pinotdb import connect

app = FastAPI(title="EVFleet Management API", version="1.0")

# Configuración de CORS para permitir peticiones desde el Frontend (React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de servicios
PB_URL = os.getenv("PB_URL", "http://host.docker.internal:8090")
PB_EMAIL = "jalvarezp3@uteq.edu.ec"  # Credenciales de tu contexto
PB_PASS = "Jeremy2004"

# Variable global para cachear el token de PocketBase
_pb_token = None

def pb_headers():
    """Obtiene el token de administrador de PocketBase."""
    global _pb_token
    if _pb_token:
        return {"Authorization": f"Bearer {_pb_token}"}
        
    try:
        r = requests.post(f"{PB_URL}/api/collections/_superusers/auth-with-password",
            json={"identity": PB_EMAIL, "password": PB_PASS})
        if r.status_code != 200:
            r = requests.post(f"{PB_URL}/api/admins/auth-with-password",
                json={"identity": PB_EMAIL, "password": PB_PASS})
        
        _pb_token = r.json()['token']
        return {"Authorization": f"Bearer {_pb_token}"}
    except Exception:
        raise HTTPException(status_code=500, detail="Error de autenticación con PocketBase")

def pinot_query(sql: str):
    """Ejecuta una consulta SQL en el Broker de Pinot."""
    try:
        pinot_host = os.getenv("PINOT_HOST", "host.docker.internal")
        conn = connect(host=pinot_host, port=8099, path="/query/sql")
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en Pinot: {str(e)}")

# ─── DASHBOARD (Servir HTML) ──────────────────────────────

@app.get("/")
def root():
    return FileResponse("index.html")

# ─── CRUD VEHÍCULOS (PocketBase) ───────────────────────────

@app.get("/vehicles/")
def listar_vehiculos():
    r = requests.get(f"{PB_URL}/api/collections/electric_vehicles/records",
        params={"perPage": 200}, headers=pb_headers())
    return r.json().get("items", [])

@app.post("/vehicles/")
def crear_vehiculo(data: dict):
    
    r = requests.post(f"{PB_URL}/api/collections/electric_vehicles/records",
        json=data, headers=pb_headers())
    if r.status_code not in (200, 201): raise HTTPException(400, r.text)
    return r.json()

@app.put("/vehicles/{id}")
def actualizar_vehiculo(id: str, data: dict):
    # PocketBase usa PATCH para actualizaciones parciales
    r = requests.patch(f"{PB_URL}/api/collections/electric_vehicles/records/{id}",
        json=data, headers=pb_headers())
    return r.json()

@app.delete("/vehicles/{id}")
def eliminar_vehiculo(id: str):
    requests.delete(f"{PB_URL}/api/collections/electric_vehicles/records/{id}",
        headers=pb_headers())
    return {"ok": True}

# ─── ANALYTICS (Apache Pinot) ──────────────────────────────

@app.get("/analytics/charging-summary")
def resumen_carga():
    # Usamos los campos reales: kwh_delivered y total_cost
    return pinot_query("""
        SELECT station_id,
               COUNT(*)             as sesiones,
               SUM(kwh_delivered)   as energia_total_kwh,
               AVG(total_cost)      as costo_promedio
        FROM fact_charging_sessions
        GROUP BY station_id
        ORDER BY energia_total_kwh DESC LIMIT 10
    """)

@app.get("/analytics/emissions-report")
def reporte_emisiones():
    # Consulta a la tabla de reportes de emisiones
    return pinot_query("""
        SELECT SUM(co2_avoided_kg) as co2_total_ahorrado,
               COUNT(DISTINCT vehicle_id) as vehiculos_monitoreados,
               AVG(km_driven) as km_promedio_recorrido
        FROM fact_emissions_reports
    """)