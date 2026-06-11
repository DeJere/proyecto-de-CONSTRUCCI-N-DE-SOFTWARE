import requests
import os
from dotenv import load_dotenv

# Cargar .env buscando en la carpeta superior (root del proyecto)
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))

if os.path.exists(dotenv_path):
    print(f"📝 Cargando configuración desde: {dotenv_path}")
    load_dotenv(dotenv_path, override=True) # override=True obliga a usar el valor del archivo
else:
    print(f"⚠️ ADVERTENCIA: No se encontró el archivo .env en {dotenv_path}")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

PB_URL = os.getenv("PB_URL", "http://127.0.0.1:8090")
PB_EMAIL = os.getenv("PB_EMAIL")
PB_PASS = os.getenv("PB_PASS")
PINOT_HOST = os.getenv("PINOT_HOST", "localhost")

# Auto-corrección: Solo si estamos en Windows
if os.name == 'nt':
    if "host.docker.internal" in PB_URL:
        PB_URL = PB_URL.replace("host.docker.internal", "127.0.0.1")
    if PINOT_HOST == "pinot-broker":
        PINOT_HOST = "localhost"

PINOT_BROKER = f"http://{PINOT_HOST}:8099/query/sql"

SERP_API_KEY = os.getenv("SERP_API_KEY", "").strip()

if not SERP_API_KEY:
    print("❌ ERROR: SERP_API_KEY no encontrada. Revisa tu archivo .env")
    exit()

if SERP_API_KEY.endswith("aqui") or "tu_clave" in SERP_API_KEY:
    print(f"❌ ERROR: La clave detectada parece ser un placeholder: ...{SERP_API_KEY[-8:]}")
    print("Por favor, asegúrate de que en el archivo .env no diga 'aqui' al final.")
    exit()
else:
    print(f"✅ SERP_API_KEY detectada (comienza en {SERP_API_KEY[:4]}... y termina en ...{SERP_API_KEY[-4:]})")

# ─────────────────────────────────────────────
# LOGIN POCKETBASE
# ─────────────────────────────────────────────

print("LOGIN POCKETBASE...")

auth = requests.post(
    f"{PB_URL}/api/collections/_superusers/auth-with-password",
    json={
        "identity": PB_EMAIL,
        "password": PB_PASS
    }
)

if auth.status_code != 200:
    print("ERROR LOGIN")
    print(auth.text)
    exit()

token = auth.json()["token"]

headers = {
    "Authorization": f"Bearer {token}"
}

print("LOGIN OK")

# ─────────────────────────────────────────────
# CREAR CARPETA DESCARGAS
# ─────────────────────────────────────────────

os.makedirs("downloads", exist_ok=True)

# ─────────────────────────────────────────────
# OBTENER VEHÍCULOS DESDE PINOT
# ─────────────────────────────────────────────

sql = """
SELECT
    make,
    model,
    model_year,
    dol_vehicle_id
FROM dim_electric_vehicles
LIMIT 500
"""

print("CONSULTANDO PINOT...")

response = requests.post(
    PINOT_BROKER,
    json={"sql": sql}
)

if response.status_code != 200:
    print("ERROR PINOT")
    print(response.text)
    exit()

data = response.json()

rows = data["resultTable"]["rows"]

print(f"VEHICULOS ENCONTRADOS: {len(rows)}")

# ─────────────────────────────────────────────
# LOOP VEHICULOS
# ─────────────────────────────────────────────

for row in rows:

    try:

        make = str(row[0])
        model = str(row[1])
        year = str(row[2])
        dol_id = str(row[3])

        vehicle_name = f"{make} {model} {year}"

        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"BUSCANDO: {vehicle_name}")

        # ─────────────────────────────────────
        # EVITAR DUPLICADOS: Verificar si el ID ya existe
        # ─────────────────────────────────────
        check_res = requests.get(
            f"{PB_URL}/api/collections/products/records",
            headers=headers,
            params={"filter": f'vehicle_id="{dol_id}"'}
        )
        if check_res.status_code == 200 and check_res.json().get("totalItems", 0) > 0:
            print(f"SALTANDO: El vehículo {dol_id} ya tiene una imagen registrada.")
            continue

        # ─────────────────────────────────────
        # BUSCAR IMAGEN
        # ─────────────────────────────────────

        search_url = "https://serpapi.com/search.json"

        params = {
            "engine": "google_images",
            "q": vehicle_name,
            "api_key": SERP_API_KEY
        }

        r = requests.get(
            search_url,
            params=params,
            timeout=30
        )

        if r.status_code == 401:
            print(f"❌ ERROR CRÍTICO: La SERP_API_KEY es inválida.")
            print(f"Detalle: {r.text}")
            break  # Detener el script por completo

        if r.status_code != 200:
            print(f"❌ ERROR DE API (Status {r.status_code}): {r.text}")
            continue

        result = r.json()
        
        if "error" in result:
            print(f"❌ ERROR DE SERPAPI: {result['error']}")
            continue

        images = result.get("images_results", [])

        if len(images) == 0:
            print("NO SE ENCONTRO IMAGEN")
            continue

        # Variedad: elegir una imagen distinta entre los primeros 5 resultados usando el ID
        img_idx = int(dol_id) % min(len(images), 5)
        image_url = images[img_idx]["original"]

        print("IMAGEN:")
        print(image_url)

        # ─────────────────────────────────────
        # DESCARGAR IMAGEN
        # ─────────────────────────────────────

        img_response = requests.get(
            image_url,
            timeout=30
        )

        if img_response.status_code != 200:
            print("ERROR DESCARGANDO")
            continue

        filename = f"downloads/{dol_id}.jpg"

        with open(filename, "wb") as f:
            f.write(img_response.content)

        print("IMAGEN DESCARGADA")

        # ─────────────────────────────────────
        # SUBIR A POCKETBASE
        # ─────────────────────────────────────

        data_pb = {
            "name": vehicle_name,
            "vehicle_id": dol_id,
            "image_status": True
        }

        with open(filename, "rb") as img:

            files = {
                "image": img
            }

            created = requests.post(
                f"{PB_URL}/api/collections/products/records",
                headers=headers,
                data=data_pb,
                files=files,
                timeout=60
            )

        # ─────────────────────────────────────
        # RESPUESTA
        # ─────────────────────────────────────

        if created.status_code in [200, 201]:

            print("SUBIDO A POCKETBASE OK")

        else:

            print("ERROR SUBIENDO A POCKETBASE")
            print(created.status_code)
            print(created.text)

    except Exception as e:

        print("ERROR GENERAL:")
        print(str(e))

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TERMINADO")