"""
Repara PocketBase: elimina las colecciones existentes, las recrea con
el schema correcto y migra todos los datos desde PostgreSQL.
"""

import psycopg2
import decimal
import requests
import json

# ─── CONFIGURACIÓN ────────────────────────────────────────────────
PG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "evfleet_vehicle",
    "user":     "postgres",
    "password": "Jeremy2004",
}

PB_URL    = "http://127.0.0.1:8090"
PB_EMAIL  = "jalvarezp3@uteq.edu.ec"
PB_PASS   = "Jeremy2004"
# ──────────────────────────────────────────────────────────────────

SCHEMAS = [
    {
        "name": "manufacturers",
        "fields": [
            {"name": "manufacturer_id",   "type": "number"},
            {"name": "name",              "type": "text"},
            {"name": "country",           "type": "text"},
            {"name": "manufacturer_type", "type": "text"},
            {"name": "active",            "type": "bool"},
            {"name": "created_at",        "type": "date"},
        ]
    },
    {
        "name": "vehicle_models",
        "fields": [
            {"name": "model_id",         "type": "number"},
            {"name": "manufacturer_id",  "type": "number"},
            {"name": "model_name",       "type": "text"},
            {"name": "vehicle_type",     "type": "text"},
            {"name": "base_range_miles", "type": "number"},
            {"name": "release_year",     "type": "number"},
        ]
    },
    {
        "name": "electric_vehicles",
        "fields": [
            {"name": "vehicle_id",            "type": "number"},
            {"name": "vin",                   "type": "text"},
            {"name": "county",                "type": "text"},
            {"name": "city",                  "type": "text"},
            {"name": "state",                 "type": "text"},
            {"name": "postal_code",           "type": "text"},
            {"name": "model_year",            "type": "number"},
            {"name": "make",                  "type": "text"},
            {"name": "model",                 "type": "text"},
            {"name": "electric_vehicle_type", "type": "text"},
            {"name": "cafv_eligibility",      "type": "text"},
            {"name": "electric_range",        "type": "number"},
            {"name": "legislative_district",  "type": "number"},
            {"name": "dol_vehicle_id",        "type": "number"},
            {"name": "vehicle_location",      "type": "text"},
            {"name": "electric_utility",      "type": "text"},
            {"name": "census_tract",          "type": "text"},
        ]
    },
    {
        "name": "customers",
        "fields": [
            {"name": "customer_id",       "type": "number"},
            {"name": "first_name",        "type": "text"},
            {"name": "last_name",         "type": "text"},
            {"name": "email",             "type": "text"},
            {"name": "phone",             "type": "text"},
            {"name": "city",              "type": "text"},
            {"name": "state",             "type": "text"},
            {"name": "postal_code",       "type": "text"},
            {"name": "registration_date", "type": "date"},
            {"name": "active",            "type": "bool"},
        ]
    },
    {
        "name": "employees",
        "fields": [
            {"name": "employee_id", "type": "number"},
            {"name": "first_name",  "type": "text"},
            {"name": "last_name",   "type": "text"},
            {"name": "role",        "type": "text"},
            {"name": "department",  "type": "text"},
            {"name": "email",       "type": "text"},
            {"name": "phone",       "type": "text"},
            {"name": "hire_date",   "type": "date"},
            {"name": "salary",      "type": "number"},
            {"name": "active",      "type": "bool"},
        ]
    },
    {
        "name": "charging_stations",
        "fields": [
            {"name": "station_id",       "type": "number"},
            {"name": "name",             "type": "text"},
            {"name": "address",          "type": "text"},
            {"name": "city",             "type": "text"},
            {"name": "state",            "type": "text"},
            {"name": "charger_type",     "type": "text"},
            {"name": "power_kw",         "type": "number"},
            {"name": "num_connectors",   "type": "number"},
            {"name": "electric_utility", "type": "text"},
            {"name": "latitude",         "type": "number"},
            {"name": "longitude",        "type": "number"},
            {"name": "active",           "type": "bool"},
        ]
    },
    {
        "name": "charging_sessions",
        "fields": [
            {"name": "session_id",     "type": "number"},
            {"name": "vehicle_id",     "type": "number"},
            {"name": "station_id",     "type": "number"},
            {"name": "customer_id",    "type": "number"},
            {"name": "start_time",     "type": "date"},
            {"name": "end_time",       "type": "date"},
            {"name": "kwh_delivered",  "type": "number"},
            {"name": "total_cost",     "type": "number"},
            {"name": "session_status", "type": "text"},
        ]
    },
    {
        "name": "inspections",
        "fields": [
            {"name": "inspection_id",   "type": "number"},
            {"name": "vehicle_id",      "type": "number"},
            {"name": "inspection_date", "type": "date"},
            {"name": "inspection_type", "type": "text"},
            {"name": "result",          "type": "text"},
            {"name": "notes",           "type": "text"},
            {"name": "inspector_name",  "type": "text"},
        ]
    },
    {
        "name": "maintenance_alerts",
        "fields": [
            {"name": "alert_id",    "type": "number"},
            {"name": "vehicle_id",  "type": "number"},
            {"name": "alert_type",  "type": "text"},
            {"name": "severity",    "type": "text"},
            {"name": "description", "type": "text"},
            {"name": "alert_date",  "type": "date"},
            {"name": "resolved",    "type": "bool"},
            {"name": "resolved_by", "type": "number"},
        ]
    },
    {
        "name": "emissions_reports",
        "fields": [
            {"name": "report_id",        "type": "number"},
            {"name": "vehicle_id",       "type": "number"},
            {"name": "report_year",      "type": "number"},
            {"name": "report_month",     "type": "number"},
            {"name": "km_driven",        "type": "number"},
            {"name": "kwh_consumed",     "type": "number"},
            {"name": "co2_avoided_kg",   "type": "number"},
            {"name": "fuel_savings_usd", "type": "number"},
            {"name": "generated_at",     "type": "date"},
        ]
    },
    {
        "name": "service_contracts",
        "fields": [
            {"name": "contract_id",           "type": "number"},
            {"name": "customer_id",           "type": "number"},
            {"name": "vehicle_id",            "type": "number"},
            {"name": "plan_type",             "type": "text"},
            {"name": "start_date",            "type": "date"},
            {"name": "end_date",              "type": "date"},
            {"name": "monthly_fee",           "type": "number"},
            {"name": "includes_inspections",  "type": "bool"},
            {"name": "includes_roadside",     "type": "bool"},
            {"name": "active",                "type": "bool"},
        ]
    },
]


def make_field(name, tipo):
    base = {"name": name, "required": False}
    if tipo == "number":
        return {**base, "type": "number", "options": {"min": None, "max": None, "noDecimal": False}}
    if tipo == "bool":
        return {**base, "type": "bool"}
    if tipo == "date":
        return {**base, "type": "date", "options": {"min": "", "max": ""}}
    return {**base, "type": "text", "options": {"min": None, "max": None, "pattern": ""}}


def serialize(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, decimal.Decimal):
        return float(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


# ─── AUTENTICACIÓN ────────────────────────────────────────────────
print("🔐 Autenticando en PocketBase...")
for endpoint in [
    f"{PB_URL}/api/collections/_superusers/auth-with-password",
    f"{PB_URL}/api/admins/auth-with-password",
]:
    res = requests.post(endpoint, json={"identity": PB_EMAIL, "password": PB_PASS})
    if res.status_code != 404:
        res.raise_for_status()
        token = res.json()["token"]
        break
headers = {"Authorization": f"Bearer {token}"}
print("✅ Autenticado\n")

# ─── PASO 1: ELIMINAR COLECCIONES EXISTENTES ─────────────────────
print("🗑️  Eliminando colecciones existentes...")
# Eliminar en orden inverso para respetar dependencias
for schema in reversed(SCHEMAS):
    name = schema["name"]
    # Obtener ID de la colección
    r = requests.get(f"{PB_URL}/api/collections/{name}", headers=headers)
    if r.status_code == 200:
        col_id = r.json()["id"]
        d = requests.delete(f"{PB_URL}/api/collections/{col_id}", headers=headers)
        if d.status_code == 204:
            print(f"  ✓ '{name}' eliminada")
        else:
            print(f"  ✗ '{name}' error al eliminar: {d.text[:100]}")
    else:
        print(f"  · '{name}' no existe, se omite")

# ─── PASO 2: CREAR COLECCIONES CON SCHEMA CORRECTO ───────────────
print("\n📋 Creando colecciones con schema correcto...")
for schema in SCHEMAS:
    name = schema["name"]
    fields = [make_field(f["name"], f["type"]) for f in schema["fields"]]
    payload = {"name": name, "type": "base", "fields": fields}
    r = requests.post(f"{PB_URL}/api/collections", json=payload, headers=headers)
    if r.status_code == 200:
        print(f"  ✓ '{name}' creada ({len(fields)} campos)")
    else:
        print(f"  ✗ '{name}' error: {r.text[:200]}")

# ─── PASO 3: MIGRAR DATOS DESDE POSTGRESQL ───────────────────────
print("\n📥 Conectando a PostgreSQL...")
conn = psycopg2.connect(**PG)
cur = conn.cursor()
print("✅ Conexión exitosa\n")

BATCH_SIZE = 50  # PocketBase no tiene endpoint batch nativo, usamos hilos

import concurrent.futures

print("🚀 Migrando datos...")
session = requests.Session()
session.headers.update(headers)

def insert_record(url, record):
    try:
        r = session.post(url, json=record, timeout=30)
        return r.status_code == 200, r.text[:150] if r.status_code != 200 else ""
    except Exception as e:
        return False, str(e)

for schema in SCHEMAS:
    table = schema["name"]
    print(f"\n  [{table}]")
    try:
        cur.execute(f'SELECT * FROM "{table}"')
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        total = len(rows)
        print(f"  → {total} filas")

        if total == 0:
            print("  · Tabla vacía, se omite")
            continue

        inserted, errors = 0, 0
        url = f"{PB_URL}/api/collections/{table}/records"
        records = [{col: serialize(val) for col, val in zip(columns, row)} for row in rows]

        # Inserción paralela con hasta 10 hilos
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(insert_record, url, rec): i for i, rec in enumerate(records)}
            for future in concurrent.futures.as_completed(futures):
                ok, msg = future.result()
                if ok:
                    inserted += 1
                else:
                    errors += 1
                    if errors <= 2:
                        print(f"    ✗ {msg}")
                # Progreso cada 10%
                done = inserted + errors
                if done % max(1, total // 10) == 0:
                    print(f"    {done}/{total} procesados...", end="\r")

        print(f"  ✅ {inserted}/{total} insertados, {errors} errores      ")

    except Exception as e:
        print(f"  ❌ Error: {e}")

session.close()
cur.close()
conn.close()

print("\n✅ ¡Reparación completada!")
