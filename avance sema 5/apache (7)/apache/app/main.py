import os
import logging
import requests
import httpx
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG FASTAPI
# ─────────────────────────────────────────────

app = FastAPI(title="EVFleet Management API", version="1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─────────────────────────────────────────────
# VARIABLES
# ─────────────────────────────────────────────

PB_URL     = os.getenv("PB_URL", "http://127.0.0.1:8090")
PB_EMAIL   = os.getenv("PB_EMAIL")
PB_PASS    = os.getenv("PB_PASS")
PINOT_HOST = os.getenv("PINOT_HOST", "localhost")

# Auto-corrección: Solo si estamos en Windows (PowerShell/CMD) fuera de Docker
if os.name == 'nt':
    if "host.docker.internal" in PB_URL: PB_URL = PB_URL.replace("host.docker.internal", "127.0.0.1")
    if PINOT_HOST == "pinot-broker":     PINOT_HOST = "localhost"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("--- CONFIGURACIÓN CARGADA ---")
print(f"PB_URL: {PB_URL}")
print(f"PB_EMAIL: {'Configurado' if PB_EMAIL else 'FALTANTE'}")
print(f"PINOT_HOST: {PINOT_HOST}")
print("-----------------------------")

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
            json={"identity": PB_EMAIL, "password": PB_PASS}, timeout=10
        )
        if r.status_code != 200:
            raise Exception(f"LOGIN ERROR: {r.text}")
        _pb_token = r.json()["token"]
        return {"Authorization": f"Bearer {_pb_token}"}
    except Exception as e:
        logger.error(f"PocketBase auth error: {e}")
        raise HTTPException(status_code=500, detail="PocketBase auth error")

# ─────────────────────────────────────────────
# APACHE PINOT
# ─────────────────────────────────────────────

def pinot_query(sql: str):
    try:
        r = requests.post(
            f"http://{PINOT_HOST}:8099/query/sql",
            json={"sql": sql}, timeout=15
        )
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Pinot error: {r.text}")
        data = r.json()
        if "resultTable" not in data:
            return []
        rt   = data["resultTable"]
        cols = [c.lower().split('.')[-1] for c in rt.get("columnNames", [])]
        return [dict(zip(cols, row)) for row in rt.get("rows", [])]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pinot query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# HTML
# ─────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def serve(template: str):
    path = os.path.join(BASE_DIR, "templates", template)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"{template} no encontrado")
    return FileResponse(path)

@app.get("/")
def root(): return serve("index.html")

@app.get("/catalog")
def catalog(): return serve("vehicle_electric.html")

@app.get("/stations")
def stations(): return serve("stations.html")

@app.get("/admin/products")
def admin_products(): return serve("products_admin.html")

# ─────────────────────────────────────────────
# VEHÍCULOS DESDE PINOT
# ─────────────────────────────────────────────

@app.get("/vehicles/")
def listar_vehiculos(make:str="", year:int=None, vehicle_type:str="",
                     search:str="", page:int=1, page_size:int=12):
    filters = []
    if make:         filters.append(f"make = '{make}'")
    if year:         filters.append(f"model_year = {year}")
    if vehicle_type: filters.append(f"electric_vehicle_type = '{vehicle_type}'")
    if search:
        s = search.replace("'","")
        filters.append(f"(make LIKE '%{s}%' OR model LIKE '%{s}%')")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    offset = (page - 1) * page_size
    return pinot_query(f"""
        SELECT vehicle_id, make, model, model_year,
               dol_vehicle_id, electric_vehicle_type, electric_range, city
        FROM dim_electric_vehicles {where}
        ORDER BY dol_vehicle_id ASC
        LIMIT {page_size} OFFSET {offset}
    """)

# ✅ NUEVO: endpoint para poblar el select de marcas
@app.get("/vehicles/makes")
def listar_makes():
    return pinot_query("""
        SELECT make, COUNT(*) as total FROM dim_electric_vehicles
        GROUP BY make ORDER BY make ASC LIMIT 200
    """)

# ✅ NUEVO: endpoint para poblar el select de años
@app.get("/vehicles/years")
def listar_years():
    return pinot_query("""
        SELECT model_year FROM dim_electric_vehicles
        GROUP BY model_year ORDER BY model_year DESC LIMIT 50
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products/")
def list_products():
    try:
        items = get_pb_collection("products", 1000)
        for item in items:
            if item.get("image"):
                item["image_url"] = f"/image-proxy/products/{item['id']}/{item['image']}"
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/products")
async def create_product(
    name: str = Form(...),
    description: str = Form(""),
    image: UploadFile = File(None)
):
    """Crear producto en PocketBase con imagen opcional"""
    try:
        data   = {"name": name, "description": description}
        files  = {}
        if image:
            content = await image.read()
            files["image"] = (image.filename, content, image.content_type)
        if files:
            r = requests.post(
                f"{PB_URL}/api/collections/products/records",
                data=data, files=files, headers=pb_headers(), timeout=15
            )
        else:
            r = requests.post(
                f"{PB_URL}/api/collections/products/records",
                json=data, headers=pb_headers(), timeout=15
            )
        if r.status_code not in (200, 201):
            raise Exception(r.text)
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ NUEVO: proxy de imágenes
@app.get("/image-proxy/{collection}/{record_id}/{filename}")
async def image_proxy(collection: str, record_id: str, filename: str):
    url = f"{PB_URL}/api/files/{collection}/{record_id}/{filename}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
    return Response(content=r.content,
                    media_type=r.headers.get("content-type", "image/jpeg"))
    
# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

@app.get("/analytics/emissions-report")
def analytics_emissions():
    return pinot_query("""
        SELECT SUM(co2_avoided_kg) as co2_total_ahorrado,
               COUNT(DISTINCT vehicle_id) as vehiculos_monitoreados,
               AVG(km_driven) as km_promedio_recorrido
        FROM fact_emissions_reports
    """)

@app.get("/analytics/vehicles-list")
def analytics_vehicles_list():
    return pinot_query("""
        SELECT vehicle_id, make, model, model_year, city, electric_vehicle_type
        FROM dim_electric_vehicles LIMIT 10
    """)

@app.get("/analytics/charging-summary")
def analytics_charging():
    return pinot_query("""
        SELECT station_id, SUM(kwh_delivered) as energia_total_kwh
        FROM fact_charging_sessions
        GROUP BY station_id ORDER BY energia_total_kwh DESC LIMIT 5
    """)

# ── NUEVO: detalle de estaciones con costo y sesiones ────
@app.get("/analytics/charging-detail")
def analytics_charging_detail():
    return pinot_query("""
        SELECT station_id,
               AVG(charging_cost)  as costo_promedio,
               COUNT(*)            as total_sesiones,
               SUM(kwh_delivered)  as kwh_total
        FROM fact_charging_sessions
        GROUP BY station_id
        ORDER BY kwh_total DESC
        LIMIT 10
    """)

@app.get("/analytics/vehicles")
def analytics_vehicles():
    return pinot_query("""
        SELECT make, COUNT(*) as total FROM dim_electric_vehicles
        GROUP BY make ORDER BY total DESC LIMIT 10
    """)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)