"""
Crea las 11 colecciones en PocketBase y migra todos los datos desde PostgreSQL.
Requisitos:
  python -m pip install psycopg2-binary requests

Uso:
  python migrar_postgres_a_pocketbase.py
"""

import psycopg2
import decimal
import requests

# ─── CONFIGURACIÓN ────────────────────────────────────────────────
PG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "evfleet_vehicle",
    "user":     "postgres",
    "password": "Jeremy2004",
}

PB_URL         = "http://127.0.0.1:8090"
PB_ADMIN_EMAIL = "jalvarezp3@uteq.edu.ec"   # <-- cambia esto
PB_ADMIN_PASS  = "Jeremy2004"    # <-- cambia esto
# ──────────────────────────────────────────────────────────────────


# ─── ESQUEMA DE COLECCIONES ───────────────────────────────────────
# Define cada colección con sus campos y tipos para PocketBase
SCHEMAS = [
    {
        "name": "manufacturers",
        "fields": [
            {"name": "manufacturer_id", "type": "number"},
            {"name": "name",            "type": "text"},
            {"name": "country",         "type": "text"},
            {"name": "manufacturer_type","type": "text"},
            {"name": "active",          "type": "bool"},
            {"name": "created_at",      "type": "date"},
        ]
    },
    {
        "name": "vehicle_models",
        "fields": [
            {"name": "model_id",          "type": "number"},
            {"name": "manufacturer_id",   "type": "number"},
            {"name": "model_name",        "type": "text"},
            {"name": "vehicle_type",      "type": "text"},
            {"name": "base_range_miles",  "type": "number"},
            {"name": "release_year",      "type": "number"},
        ]
    },
    {
        "name": "electric_vehicles",
        "fields": [
            {"name": "vehicle_id",           "type": "number"},
            {"name": "vin",                  "type": "text"},
            {"name": "county",               "type": "text"},
            {"name": "city",                 "type": "text"},
            {"name": "state",                "type": "text"},
            {"name": "postal_code",          "type": "text"},
            {"name": "model_year",           "type": "number"},
            {"name": "make",                 "type": "text"},
            {"name": "model",                "type": "text"},
            {"name": "electric_vehicle_type","type": "text"},
            {"name": "cafv_eligibility",     "type": "text"},
            {"name": "electric_range",       "type": "number"},
            {"name": "legislative_district", "type": "number"},
            {"name": "dol_vehicle_id",       "type": "number"},
            {"name": "vehicle_location",     "type": "text"},
            {"name": "electric_utility",     "type": "text"},
            {"name": "census_tract",         "type": "text"},
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
            {"name": "station_id",      "type": "number"},
            {"name": "name",            "type": "text"},
            {"name": "address",         "type": "text"},
            {"name": "city",            "type": "text"},
            {"name": "state",           "type": "text"},
            {"name": "charger_type",    "type": "text"},
            {"name": "power_kw",        "type": "number"},
            {"name": "num_connectors",  "type": "number"},
            {"name": "electric_utility","type": "text"},
            {"name": "latitude",        "type": "number"},
            {"name": "longitude",       "type": "number"},
            {"name": "active",          "type": "bool"},
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
            {"name": "report_id",       "type": "number"},
            {"name": "vehicle_id",      "type": "number"},
            {"name": "report_year",     "type": "number"},
            {"name": "report_month",    "type": "number"},
            {"name": "km_driven",       "type": "number"},
            {"name": "kwh_consumed",    "type": "number"},
            {"name": "co2_avoided_kg",  "type": "number"},
            {"name": "fuel_savings_usd","type": "number"},
            {"name": "generated_at",    "type": "date"},
        ]
    },
    {
        "name": "service_contracts",
        "fields": [
            {"name": "contract_id",          "type": "number"},
            {"name": "customer_id",          "type": "number"},
            {"name": "vehicle_id",           "type": "number"},
            {"name": "plan_type",            "type": "text"},
            {"name": "start_date",           "type": "date"},
            {"name": "end_date",             "type": "date"},
            {"name": "monthly_fee",          "type": "number"},
            {"name": "includes_inspections", "type": "bool"},
            {"name": "includes_roadside",    "type": "bool"},
            {"name": "active",               "type": "bool"},
        ]
    },
]

# Mapeo de tipos PocketBase a su estructura de campo
def make_field(name, tipo):
    base = {"name": name, "required": False}
    if tipo == "number":
        return {**base, "type": "number", "options": {"min": None, "max": None, "noDecimal": False}}
    if tipo == "bool":
        return {**base, "type": "bool"}
    if tipo == "date":
        return {**base, "type": "date", "options": {"min": "", "max": ""}}
    # texto por defecto
    return {**base, "type": "text", "options": {"min": None, "max": None, "pattern": ""}}


def get_admin_token():
    for endpoint in [
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        f"{PB_URL}/api/admins/auth-with-password",
    ]:
        res = requests.post(
            endpoint,
            json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
        )
        if res.status_code != 404:
            res.raise_for_status()
            return res.json()["token"]
    raise RuntimeError("No se pudo encontrar el endpoint de autenticación de admin.")


def create_collections(headers):
    print("\n── Creando colecciones ──────────────────────")
    for schema in SCHEMAS:
        name = schema["name"]
        fields = [make_field(f["name"], f["type"]) for f in schema["fields"]]
        payload = {
            "name": name,
            "type": "base",
            "schema": fields,
        }
        res = requests.post(f"{PB_URL}/api/collections", json=payload, headers=headers)
        if res.status_code == 200:
            print(f"  ✓ '{name}' creada")
        elif "already exists" in res.text:
            print(f"  · '{name}' ya existe, se omite")
        else:
            print(f"  ✗ '{name}' error: {res.text[:200]}")
    print()


def serialize(val):
    """Convierte tipos de PostgreSQL a tipos serializables por JSON."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, decimal.Decimal):
        return float(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def migrate_table(cur, headers, table):
    cur.execute(f'SELECT * FROM "{table}"')
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()

    if not rows:
        print(f"  ! Tabla vacía, se omite.\n")
        return

    url = f"{PB_URL}/api/collections/{table}/records"
    inserted, errors = 0, 0

    # Usar sesión persistente para reutilizar conexiones TCP
    session = requests.Session()
    session.headers.update(headers)

    for row in rows:
        record = {col: serialize(val) for col, val in zip(columns, row)}

        try:
            res = session.post(url, json=record)
            if res.status_code == 200:
                inserted += 1
            else:
                errors += 1
                print(f"    ✗ {res.text[:200]}")
        except Exception as e:
            errors += 1
            print(f"    ✗ excepción: {e}")

    session.close()
    print(f"  → {inserted}/{len(rows)} insertados, {errors} errores\n")


if __name__ == "__main__":
    # 1. Conectar a PostgreSQL
    print("Conectando a PostgreSQL...")
    conn = psycopg2.connect(**PG)
    cur = conn.cursor()
    print("Conexión exitosa ✓")

    # 2. Autenticar en PocketBase
    print("Autenticando en PocketBase...")
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    print("Token obtenido ✓")

    # 3. Crear colecciones
    create_collections(headers)

    # 4. Migrar datos
    print("── Migrando datos ───────────────────────────")
    tables = [s["name"] for s in SCHEMAS]
    for i, table in enumerate(tables, 1):
        print(f"[{i}/{len(tables)}] '{table}'...")
        try:
            migrate_table(cur, headers, table)
        except Exception as e:
            print(f"  ✗ Error: {e}\n")

    cur.close()
    conn.close()
    print("¡Todo listo!")
