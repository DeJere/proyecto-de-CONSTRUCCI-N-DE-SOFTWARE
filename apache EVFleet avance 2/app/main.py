import os
import logging
import requests
import httpx                          # ← agregar
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response  # ← agregar Response


load_dotenv()

# ─────────────────────────────────────────────
# CONFIG FASTAPI
# ─────────────────────────────────────────────

app = FastAPI(title="EVFleet Management API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# VARIABLES
# ─────────────────────────────────────────────

PB_URL      = os.getenv("PB_URL", "http://127.0.0.1:8090")
PB_EMAIL    = os.getenv("PB_EMAIL")
PB_PASS     = os.getenv("PB_PASS")
PINOT_HOST  = os.getenv("PINOT_HOST", "localhost")

# Auto-corrección: Solo si estamos en Windows (PowerShell/CMD) fuera de Docker
if os.name == 'nt':
    if "host.docker.internal" in PB_URL: PB_URL = PB_URL.replace("host.docker.internal", "127.0.0.1")
    if PINOT_HOST == "pinot-broker": PINOT_HOST = "localhost"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("--- CONFIGURACIÓN CARGADA ---")
print(f"PB_URL: {PB_URL}")
print(f"PB_EMAIL: {'Configurado' if PB_EMAIL else 'FALTANTE'}")
print(f"PINOT_HOST: {PINOT_HOST}")
print("-----------------------------")

if not PB_EMAIL or not PB_PASS:
    logger.warning("⚠️ PB_EMAIL o PB_PASS no configurados.")

# ─────────────────────────────────────────────
# AUTH POCKETBASE
# ─────────────────────────────────────────────

_pb_token = None

def pb_headers():
    global _pb_token
    if _pb_token:
        return {"Authorization": f"Bearer {_pb_token}"}
    try:
        r = requests.post(
            f"{PB_URL}/api/collections/_superusers/auth-with-password",
            json={"identity": PB_EMAIL, "password": PB_PASS},
            timeout=10
        )
        if r.status_code != 200:
            logger.error(r.text)
            raise Exception("LOGIN ERROR")
        _pb_token = r.json()["token"]
        return {"Authorization": f"Bearer {_pb_token}"}
    except Exception as e:
        logger.error(f"Fallo login en: {PB_URL} con usuario {PB_EMAIL} — {e}")
        raise HTTPException(status_code=500, detail="PocketBase auth error")

# ─────────────────────────────────────────────
# APACHE PINOT
# ─────────────────────────────────────────────

async def query_pinot(sql: str):
    broker_url = f"http://{PINOT_HOST}:8099/query/sql"
    payload = {"sql": sql}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(broker_url, json=payload)

    response.raise_for_status()
    data = response.json()

    result_table = data.get("resultTable", {})
    rows = result_table.get("rows", [])
    schema = result_table.get("dataSchema", {})
    
    # Normalizamos los nombres de las columnas (minúsculas y sin prefijos de tabla)
    columns = [c.lower().split('.')[-1] for c in schema.get("columnNames", [])]

    resultados = []
    for row in rows:
        item = {}
        for i, value in enumerate(row):
            if i < len(columns):
                item[columns[i]] = value
        resultados.append(item)

    return resultados

# ─────────────────────────────────────────────
# HTML
# ─────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
def root():
    path = os.path.join(BASE_DIR, "templates", "index.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="index.html no encontrado")
    return FileResponse(path)

@app.get("/catalog")
def catalog():
    path = os.path.join(BASE_DIR, "templates", "vehicle_electric.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="vehicle_electric.html no encontrado")
    return FileResponse(path)

# ─────────────────────────────────────────────
# VEHÍCULOS DESDE PINOT
# ─────────────────────────────────────────────

@app.get("/vehicles/")
async def listar_vehiculos(
    make: str = "",
    year: int = None,
    vehicle_type: str = "",
    search: str = "",
    page: int = 1,
    page_size: int = 100
):
    filters = []
    if make:
        filters.append(f"make = '{make}'")
    if year:
        filters.append(f"model_year = {year}")
    if vehicle_type:
        filters.append(f"electric_vehicle_type = '{vehicle_type}'")
    if search:
        # Pinot soporta LIKE pero solo con texto simple
        safe = search.replace("'", "")
        filters.append(f"(make LIKE '%{safe}%' OR model LIKE '%{safe}%')")

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    offset = (page - 1) * page_size

    return await query_pinot(f"""
        SELECT
            vehicle_id, make, model, model_year,
            dol_vehicle_id, electric_vehicle_type,
            electric_range, city
        FROM dim_electric_vehicles
        {where}
        ORDER BY dol_vehicle_id ASC
        LIMIT {page_size}
        OFFSET {offset}
    """)

# ✅ NUEVO: endpoint para poblar el select de marcas
@app.get("/vehicles/makes")
async def listar_makes():
    return await query_pinot("""
        SELECT make, COUNT(*) as total
        FROM dim_electric_vehicles
        GROUP BY make
        ORDER BY make ASC
        LIMIT 200
    """)

# ✅ NUEVO: endpoint para poblar el select de años
@app.get("/vehicles/years")
async def listar_years():
    return await query_pinot("""
        SELECT model_year
        FROM dim_electric_vehicles
        GROUP BY model_year
        ORDER BY model_year DESC
        LIMIT 50
    """)

# ─────────────────────────────────────────────
# PRODUCTOS DESDE POCKETBASE
# ─────────────────────────────────────────────

@app.get("/pb/{collection}")
def get_pb_collection(collection: str, perPage: int = 50):
    try:
        r = requests.get(
            f"{PB_URL}/api/collections/{collection}/records?perPage={perPage}",
            headers=pb_headers(),
            timeout=10
        )
        r.raise_for_status()
        return r.json()["items"]
    except Exception as e:
        logger.error(f"Error fetching {collection}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products/")
def list_products():
    try:
        items = get_pb_collection("products", 1000)
        for item in items:
            if item.get("image"):
                # ✅ ahora apunta al proxy local
                item["image_url"] = (
                    f"/image-proxy/products/{item['id']}/{item['image']}"
                )
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ NUEVO: proxy de imágenes
@app.get("/image-proxy/{collection}/{record_id}/{filename}")
async def image_proxy(collection: str, record_id: str, filename: str):
    url = f"{PB_URL}/api/files/{collection}/{record_id}/{filename}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "image/jpeg")
    )
    
# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

@app.get("/analytics/emissions-report")
async def analytics_emissions():
    return await query_pinot("""
        SELECT
            SUM(co2_avoided_kg)      as co2_total_ahorrado,
            COUNT(DISTINCT vehicle_id) as vehiculos_monitoreados,
            AVG(km_driven)           as km_promedio_recorrido
        FROM fact_emissions_reports
    """)

@app.get("/analytics/vehicles-list")
async def analytics_vehicles_list():
    return await query_pinot("""
        SELECT vehicle_id, make, model, model_year, vin
        FROM dim_electric_vehicles
        LIMIT 10
    """)

@app.get("/analytics/charging-summary")
async def analytics_charging():
    return await query_pinot("""
        SELECT station_id, SUM(kwh_delivered) as energia_total_kwh
        FROM fact_charging_sessions
        GROUP BY station_id
        ORDER BY energia_total_kwh DESC
        LIMIT 5
    """)

@app.get("/analytics/vehicles")
async def analytics_vehicles():
    return await query_pinot("""
        SELECT make, COUNT(*) as total
        FROM dim_electric_vehicles
        GROUP BY make
        ORDER BY total DESC
        LIMIT 10
    """)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)