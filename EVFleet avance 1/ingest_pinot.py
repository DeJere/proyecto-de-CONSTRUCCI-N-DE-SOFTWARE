"""
Ingesta a Apache Pinot 0.12.1.
Flujo correcto: CreateSegment (con schemaFile + tableConfigFile) -> UploadSegment
"""

import requests, json, os, subprocess, time

PINOT_CONTROLLER = "http://localhost:9000"
PINOT_BROKER     = "http://localhost:8099"
PARQUET_DIR      = "evfleet_parquet"
CONTAINER        = "apache-pinot-controller-1"

TABLES = [
    {
        "name": "fact_charging_sessions",
        "parquet": "charging_sessions.parquet",
        "time_col": "start_time",
        "inverted_index": ["vehicle_id","station_id","customer_id","session_status"],
        "schema": {
            "schemaName": "fact_charging_sessions",
            "dimensionFieldSpecs": [
                {"name":"session_id","dataType":"INT"},
                {"name":"vehicle_id","dataType":"INT"},
                {"name":"station_id","dataType":"INT"},
                {"name":"customer_id","dataType":"INT"},
                {"name":"session_status","dataType":"STRING"}
            ],
            "metricFieldSpecs": [
                {"name":"kwh_delivered","dataType":"DOUBLE"},
                {"name":"total_cost","dataType":"DOUBLE"},
                {"name":"start_time","dataType":"LONG"},
                {"name":"end_time","dataType":"LONG"}
            ]
        }
    },
    {
        "name": "dim_charging_stations",
        "parquet": "charging_stations.parquet",
        "time_col": None,
        "inverted_index": ["city","state","charger_type"],
        "schema": {
            "schemaName": "dim_charging_stations",
            "dimensionFieldSpecs": [
                {"name":"station_id","dataType":"INT"},
                {"name":"name","dataType":"STRING"},
                {"name":"address","dataType":"STRING"},
                {"name":"city","dataType":"STRING"},
                {"name":"state","dataType":"STRING"},
                {"name":"charger_type","dataType":"STRING"},
                {"name":"electric_utility","dataType":"STRING"},
                {"name":"active","dataType":"BOOLEAN"}
            ],
            "metricFieldSpecs": [
                {"name":"power_kw","dataType":"DOUBLE"},
                {"name":"num_connectors","dataType":"INT"},
                {"name":"latitude","dataType":"DOUBLE"},
                {"name":"longitude","dataType":"DOUBLE"}
            ]
        }
    },
    {
        "name": "dim_customers",
        "parquet": "customers.parquet",
        "time_col": "registration_date",
        "inverted_index": ["city","state","active"],
        "schema": {
            "schemaName": "dim_customers",
            "dimensionFieldSpecs": [
                {"name":"customer_id","dataType":"INT"},
                {"name":"first_name","dataType":"STRING"},
                {"name":"last_name","dataType":"STRING"},
                {"name":"email","dataType":"STRING"},
                {"name":"phone","dataType":"STRING"},
                {"name":"city","dataType":"STRING"},
                {"name":"state","dataType":"STRING"},
                {"name":"postal_code","dataType":"STRING"},
                {"name":"active","dataType":"BOOLEAN"}
            ],
            "metricFieldSpecs": [
                {"name":"registration_date","dataType":"LONG"}
            ]
        }
    },
    {
        "name": "dim_electric_vehicles",
        "parquet": "electric_vehicles.parquet",
        "time_col": None,
        "inverted_index": ["make","model","state","electric_vehicle_type"],
        "schema": {
            "schemaName": "dim_electric_vehicles",
            "dimensionFieldSpecs": [
                {"name":"vehicle_id","dataType":"INT"},
                {"name":"vin","dataType":"STRING"},
                {"name":"county","dataType":"STRING"},
                {"name":"city","dataType":"STRING"},
                {"name":"state","dataType":"STRING"},
                {"name":"postal_code","dataType":"STRING"},
                {"name":"make","dataType":"STRING"},
                {"name":"model","dataType":"STRING"},
                {"name":"electric_vehicle_type","dataType":"STRING"},
                {"name":"cafv_eligibility","dataType":"STRING"},
                {"name":"vehicle_location","dataType":"STRING"},
                {"name":"electric_utility","dataType":"STRING"},
                {"name":"census_tract","dataType":"STRING"}
            ],
            "metricFieldSpecs": [
                {"name":"model_year","dataType":"INT"},
                {"name":"electric_range","dataType":"INT"},
                {"name":"legislative_district","dataType":"INT"},
                {"name":"dol_vehicle_id","dataType":"LONG"}
            ]
        }
    },
    {
        "name": "dim_manufacturers",
        "parquet": "manufacturers.parquet",
        "time_col": "created_at",
        "inverted_index": ["country","manufacturer_type"],
        "schema": {
            "schemaName": "dim_manufacturers",
            "dimensionFieldSpecs": [
                {"name":"manufacturer_id","dataType":"INT"},
                {"name":"name","dataType":"STRING"},
                {"name":"country","dataType":"STRING"},
                {"name":"manufacturer_type","dataType":"STRING"},
                {"name":"active","dataType":"BOOLEAN"}
            ],
            "metricFieldSpecs": [
                {"name":"created_at","dataType":"LONG"}
            ]
        }
    },
    {
        "name": "dim_vehicle_models",
        "parquet": "vehicle_models.parquet",
        "time_col": None,
        "inverted_index": ["vehicle_type","manufacturer_id"],
        "schema": {
            "schemaName": "dim_vehicle_models",
            "dimensionFieldSpecs": [
                {"name":"model_id","dataType":"INT"},
                {"name":"manufacturer_id","dataType":"INT"},
                {"name":"model_name","dataType":"STRING"},
                {"name":"vehicle_type","dataType":"STRING"}
            ],
            "metricFieldSpecs": [
                {"name":"base_range_miles","dataType":"DOUBLE"},
                {"name":"release_year","dataType":"INT"}
            ]
        }
    },
    {
        "name": "fact_emissions_reports",
        "parquet": "emissions_reports.parquet",
        "time_col": "generated_at",
        "inverted_index": ["vehicle_id"],
        "schema": {
            "schemaName": "fact_emissions_reports",
            "dimensionFieldSpecs": [
                {"name":"report_id","dataType":"INT"},
                {"name":"vehicle_id","dataType":"INT"}
            ],
            "metricFieldSpecs": [
                {"name":"report_year","dataType":"INT"},
                {"name":"report_month","dataType":"INT"},
                {"name":"km_driven","dataType":"DOUBLE"},
                {"name":"kwh_consumed","dataType":"DOUBLE"},
                {"name":"co2_avoided_kg","dataType":"DOUBLE"},
                {"name":"fuel_savings_usd","dataType":"DOUBLE"},
                {"name":"generated_at","dataType":"LONG"}
            ]
        }
    },
    {
        "name": "dim_employees",
        "parquet": "employees.parquet",
        "time_col": "hire_date",
        "inverted_index": ["role","department"],
        "schema": {
            "schemaName": "dim_employees",
            "dimensionFieldSpecs": [
                {"name":"employee_id","dataType":"INT"},
                {"name":"first_name","dataType":"STRING"},
                {"name":"last_name","dataType":"STRING"},
                {"name":"role","dataType":"STRING"},
                {"name":"department","dataType":"STRING"},
                {"name":"email","dataType":"STRING"},
                {"name":"phone","dataType":"STRING"},
                {"name":"active","dataType":"BOOLEAN"}
            ],
            "metricFieldSpecs": [
                {"name":"salary","dataType":"DOUBLE"},
                {"name":"hire_date","dataType":"LONG"}
            ]
        }
    },
    {
        "name": "fact_inspections",
        "parquet": "inspections.parquet",
        "time_col": "inspection_date",
        "inverted_index": ["vehicle_id","inspection_type","result"],
        "schema": {
            "schemaName": "fact_inspections",
            "dimensionFieldSpecs": [
                {"name":"inspection_id","dataType":"INT"},
                {"name":"vehicle_id","dataType":"INT"},
                {"name":"inspection_type","dataType":"STRING"},
                {"name":"result","dataType":"STRING"},
                {"name":"notes","dataType":"STRING"},
                {"name":"inspector_name","dataType":"STRING"}
            ],
            "metricFieldSpecs": [
                {"name":"inspection_date","dataType":"LONG"}
            ]
        }
    },
    {
        "name": "fact_maintenance_alerts",
        "parquet": "maintenance_alerts.parquet",
        "time_col": "alert_date",
        "inverted_index": ["vehicle_id","alert_type","severity"],
        "schema": {
            "schemaName": "fact_maintenance_alerts",
            "dimensionFieldSpecs": [
                {"name":"alert_id","dataType":"INT"},
                {"name":"vehicle_id","dataType":"INT"},
                {"name":"alert_type","dataType":"STRING"},
                {"name":"severity","dataType":"STRING"},
                {"name":"description","dataType":"STRING"},
                {"name":"resolved","dataType":"BOOLEAN"}
            ],
            "metricFieldSpecs": [
                {"name":"resolved_by","dataType":"INT"},
                {"name":"alert_date","dataType":"LONG"}
            ]
        }
    },
    {
        "name": "fact_service_contracts",
        "parquet": "service_contracts.parquet",
        "time_col": "start_date",
        "inverted_index": ["customer_id","vehicle_id","plan_type"],
        "schema": {
            "schemaName": "fact_service_contracts",
            "dimensionFieldSpecs": [
                {"name":"contract_id","dataType":"INT"},
                {"name":"customer_id","dataType":"INT"},
                {"name":"vehicle_id","dataType":"INT"},
                {"name":"plan_type","dataType":"STRING"},
                {"name":"includes_inspections","dataType":"BOOLEAN"},
                {"name":"includes_roadside","dataType":"BOOLEAN"},
                {"name":"active","dataType":"BOOLEAN"}
            ],
            "metricFieldSpecs": [
                {"name":"monthly_fee","dataType":"DOUBLE"},
                {"name":"start_date","dataType":"LONG"},
                {"name":"end_date","dataType":"LONG"}
            ]
        }
    },
]


def dexec(cmd, timeout=600):
    r = subprocess.run(["docker","exec",CONTAINER]+cmd,
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout+r.stderr


def wait_for_pinot():
    print("⏳ Esperando Pinot...")
    for _ in range(30):
        try:
            r = requests.get(f"{PINOT_CONTROLLER}/instances", timeout=5)
            if r.status_code == 200:
                inst = r.json().get("instances",[])
                if any("Broker" in x for x in inst) and any("Server" in x for x in inst):
                    print("✅ Pinot listo\n"); return
        except: pass
        time.sleep(8)
    raise RuntimeError("Pinot no respondió.")


def upsert_schema(schema):
    name = schema["schemaName"]
    # Forzar eliminación para limpiar rastro de TIMESTAMP
    requests.delete(f"{PINOT_CONTROLLER}/schemas/{name}")
    r = requests.post(f"{PINOT_CONTROLLER}/schemas", json=schema)
    if r.status_code in (200,201): print(f"  ✓ Schema '{name}'")
    else: print(f"  ✗ Schema '{name}': {r.status_code} {r.text[:60]}")


def upsert_table(t):
    name = t["name"]
    # Forzar eliminación para limpiar configuración OFFLINE corrupta
    requests.delete(f"{PINOT_CONTROLLER}/tables/{name}")
    seg = {"schemaName":name,"replication":"1",
           "retentionTimeUnit":"DAYS","retentionTimeValue":"3650"}
    payload = {
        "tableName":name,"tableType":"OFFLINE",
        "segmentsConfig":seg,
        "tableIndexConfig":{"loadMode":"MMAP","invertedIndexColumns":t.get("inverted_index",[])},
        "tenants":{},"metadata":{}
    }
    r = requests.post(f"{PINOT_CONTROLLER}/tables", json=payload)
    if r.status_code in (200,201): print(f"  ✓ Tabla '{name}'")
    else: print(f"  ✗ Tabla '{name}': {r.status_code} {r.text[:60]}")


def ingest_table(t):
    name    = t["name"]
    parquet = os.path.join(PARQUET_DIR, t["parquet"])
    c_dir   = f"/tmp/pi/{name}"
    c_data  = f"{c_dir}/data"
    c_out   = f"{c_dir}/out"
    c_sch   = f"{c_dir}/schema.json"
    c_tbl   = f"{c_dir}/table.json"

    # Preparar directorios
    dexec(["rm", "-rf", c_dir])
    dexec(["mkdir", "-p", c_data, c_out])

    # Copiar parquet
    r = subprocess.run(["docker","cp",parquet,f"{CONTAINER}:{c_data}/{t['parquet']}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    ✗ cp: {r.stderr[:60]}"); return False

    # Escribir schema y table config localmente y copiar
    seg = {"schemaName":name,"replication":"1"}
    table_cfg = {
        "tableName":name,"tableType":"OFFLINE",
        "segmentsConfig":seg,
        "tableIndexConfig":{"loadMode":"MMAP"},
        "tenants":{},"metadata":{}
    }

    with open("_sch.json","w") as f: json.dump(t["schema"], f)
    with open("_tbl.json","w") as f: json.dump(table_cfg, f)
    subprocess.run(["docker","cp","_sch.json",f"{CONTAINER}:{c_sch}"], capture_output=True)
    subprocess.run(["docker","cp","_tbl.json",f"{CONTAINER}:{c_tbl}"], capture_output=True)
    os.remove("_sch.json"); os.remove("_tbl.json")

    # CreateSegment con los flags correctos
    rc, out = dexec([
        "/opt/pinot/bin/pinot-admin.sh","CreateSegment",
        "-dataDir",         c_data,
        "-format",          "PARQUET",
        "-outDir",          c_out,
        "-overwrite",
        "-schemaFile",      c_sch,
        "-tableConfigFile", c_tbl
    ], timeout=300)

    # Verificar que se creó algo
    rc2, ls_out = dexec(["find", c_out, "-mindepth","1"])
    created = [x.strip() for x in ls_out.strip().split("\n") if x.strip()]

    if not created:
        # Mostrar error relevante
        for line in out.split("\n"):
            if any(k in line for k in ["ERROR","Exception","IllegalArg","must"]):
                print(f"    ⚠ {line.strip()}")
        return False

    print(f"    → Segmento creado: {created[0]}")

    # Encontrar el .tar.gz o directorio de segmento
    tar_files = [x for x in created if x.endswith(".tar.gz")]

    if not tar_files:
        rc3, meta = dexec([
            "find", c_out,
            "-name", "metadata.properties"
        ])

        meta_files = [x.strip() for x in meta.split("\n") if x.strip()]

        if not meta_files:
            print("    ✗ No se encontró metadata.properties")
            return False

        seg_dir = os.path.dirname(meta_files[0])
        seg_name = os.path.basename(seg_dir)

        tar_path = f"{c_out}/{seg_name}.tar.gz"

        dexec(["tar","-czf",tar_path,"-C",os.path.dirname(seg_dir),seg_name])

        tar_files = [tar_path]

    # Copiar al host y subir
    local_tar = "_seg.tar.gz"
    subprocess.run(["docker","cp",f"{CONTAINER}:{tar_files[0]}",local_tar],
                   capture_output=True)

    with open(local_tar,"rb") as f:
        resp = requests.post(
            f"{PINOT_CONTROLLER}/segments",
            files={"file":(os.path.basename(tar_files[0]),f,"application/octet-stream")},
            params={"tableName":name,"tableType":"OFFLINE"},
            timeout=120
        )
    os.remove(local_tar)

    if resp.status_code in (200,201):
        print(f"    ✓ Subido al controller ({resp.status_code})")
        return True
    else:
        print(f"    ✗ Upload {resp.status_code}: {resp.text[:150]}")
        return False


if __name__ == "__main__":
    wait_for_pinot()

    print("📋 Schemas...")
    for t in TABLES: upsert_schema(t["schema"])

    print("\n📋 Tablas...")
    for t in TABLES: upsert_table(t)

    print("\n📥 Ingesta...")
    results = []
    for t in TABLES:
        p = os.path.join(PARQUET_DIR, t["parquet"])
        if not os.path.exists(p):
            print(f"\n  ⚠ Falta: {p}"); continue
        print(f"\n  [{t['name']}]")
        ok = ingest_table(t)
        results.append((t["name"], ok))

    print("\n🔍 Verificando (espera 20s)...")
    time.sleep(20)
    print(f"\n{'Tabla':<35} {'Segs':>5} {'COUNT':>10}")
    print("-"*53)
    for name, ok in results:
        try:
            rs = requests.get(f"{PINOT_CONTROLLER}/segments/{name}", timeout=10)
            segs = len(rs.json()[0].get("OFFLINE",[])) if rs.status_code==200 else "?"
        except: segs = "?"
        try:
            rq = requests.post(f"{PINOT_BROKER}/query/sql",
                               json={"sql":f"SELECT COUNT(*) FROM {name}"},timeout=15)
            count = rq.json()["resultTable"]["rows"][0][0] if "resultTable" in rq.json() else "?"
        except: count = "?"
        st = "✅" if ok else "❌"
        print(f"  {st} {name:<33} {str(segs):>5} {str(count):>10}")

    print("\n✅ Listo — UI: http://localhost:9000")
