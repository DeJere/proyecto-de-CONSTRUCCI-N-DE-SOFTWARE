import requests
import json
import os

POCKETBASE_URL = "http://localhost:8090"
ADMIN_EMAIL    = "jalvarezp3@uteq.edu.ec"
ADMIN_PASSWORD = "Jeremy2004"

# 1. Autenticarse (compatible con PocketBase v0.23+)
# Intenta primero con _superusers, luego con el endpoint legacy de admins
auth = requests.post(f"{POCKETBASE_URL}/api/collections/_superusers/auth-with-password", json={
    "identity": ADMIN_EMAIL,
    "password": ADMIN_PASSWORD
})

if auth.status_code != 200:
    # Fallback para versiones anteriores de PocketBase
    auth = requests.post(f"{POCKETBASE_URL}/api/admins/auth-with-password", json={
        "identity": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })

if auth.status_code != 200:
    print(f"Error de autenticación ({auth.status_code}): {auth.json()}")
    exit(1)

token = auth.json()["token"]
headers = {"Authorization": f"Bearer {token}"}
print("Autenticación exitosa")

# 2. Leer registros de PocketBase
pb = requests.get(
    f"{POCKETBASE_URL}/api/collections/charging_sessions/records?perPage=500",
    headers=headers
)
records = pb.json()["items"]
print(f"Registros obtenidos: {len(records)}")

# Configuración de carpeta de salida para mantener el orden
OUTPUT_DIR = "archibosjson"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 3. Guardar como JSON Lines para Pinot
file_path = os.path.join(OUTPUT_DIR, "charging_sessions.json")
with open(file_path, "w") as f:
    for r in records:
        f.write(json.dumps(r) + "\n")

print(f"Archivo {file_path} creado correctamente")