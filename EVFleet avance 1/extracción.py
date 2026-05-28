import psycopg2
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import os

# ── CONFIGURACIÓN ──────────────────────────────────────────
PG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "evfleet_vehicle",
    "user":     "postgres",
    "password": "Jeremy2004",
}

OUTPUT_DIR = "evfleet_parquet"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TABLES = [
    "charging_sessions",
    "charging_stations",
    "customers",
    "electric_vehicles",
    "emissions_reports",
    "employees",
    "inspections",
    "maintenance_alerts",
    "manufacturers",
    "service_contracts",
    "vehicle_models",
]

# ── CONEXIÓN ───────────────────────────────────────────────
print("🔐 Conectando a PostgreSQL...")
conn = psycopg2.connect(**PG)
print("✅ Conexión exitosa\n")

# ── EXTRACCIÓN Y GUARDADO ──────────────────────────────────
resumen = []
for table in TABLES:
    print(f"📥 Extrayendo: {table}")
    try:
        df = pd.read_sql(f'SELECT * FROM "{table}"', conn)

        # Convertir fechas automáticamente
        for c in df.columns:
            if any(k in c.lower() for k in ["date", "fecha", "time", "created", "updated", "at"]):
                # Convertir a milisegundos (LONG) para evitar el bug de TIMESTAMP en Pinot 0.12.1
                dt_series = pd.to_datetime(df[c], errors="coerce")
                # Convertir a milisegundos desde la época, NaT se convierte en 0
                df[c] = dt_series.astype('int64') // 10**6
                df[c] = df[c].apply(lambda x: x if x > 0 else 0)

        path = f"{OUTPUT_DIR}/{table}.parquet"
        pq.write_table(pa.Table.from_pandas(df), path, compression="snappy")
        resumen.append({"tabla": table, "registros": len(df), "columnas": df.shape[1], "archivo": path})
        print(f"   ✅ {len(df)} filas, {df.shape[1]} columnas → {path}\n")

    except Exception as e:
        print(f"   ❌ Error en {table}: {e}\n")

conn.close()

# ── RESUMEN FINAL ──────────────────────────────────────────
print("\n📊 RESUMEN DE EXTRACCIÓN:")
print("-" * 60)
for r in resumen:
    print(f"  {r['tabla']:25s} {r['registros']:8d} filas  {r['columnas']} cols")
print(f"\n✅ Archivos en carpeta: ./{OUTPUT_DIR}/")
