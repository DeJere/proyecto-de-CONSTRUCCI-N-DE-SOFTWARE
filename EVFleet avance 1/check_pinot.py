import requests, time

time.sleep(10)

BROKER = "http://localhost:8099"
CONTROLLER = "http://localhost:9000"

tables = [
    "fact_charging_sessions",
    "dim_charging_stations",
    "dim_customers",
    "dim_electric_vehicles",
    "dim_manufacturers",
    "dim_vehicle_models",
    "fact_emissions_reports",
    "dim_employees",
    "fact_inspections",
    "fact_maintenance_alerts",
    "fact_service_contracts"
]

print(f"{'Tabla':<35} {'COUNT':>10}")
print("-" * 48)
for t in tables:
    try:
        r = requests.post(f"{BROKER}/query/sql",
                          json={"sql": f"SELECT COUNT(*) FROM {t}"},
                          timeout=15)
        data = r.json()
        if "resultTable" in data:
            count = data["resultTable"]["rows"][0][0]
        elif "exceptions" in data and data["exceptions"]:
            count = data["exceptions"][0].get("message", "error")[:30]
        else:
            count = str(data)[:30]
    except Exception as e:
        count = str(e)[:30]
    print(f"{t:<35} {str(count):>10}")

# Verificar segmentos
print("\n📦 Segmentos por tabla:")
for t in tables:
    try:
        r = requests.get(f"{CONTROLLER}/segments/{t}", timeout=10)
        if r.status_code == 200:
            segs = r.json()
            offline = segs[0].get("OFFLINE", []) if segs else []
            print(f"  {t:<35} {len(offline)} segmentos")
    except Exception:
        pass
