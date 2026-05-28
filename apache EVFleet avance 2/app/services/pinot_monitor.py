import requests
import os
from dotenv import load_dotenv

load_dotenv()

PINOT_HOST = os.getenv("PINOT_HOST")
PB_EMAIL = os.getenv("PB_EMAIL")
PB_PASS = os.getenv("PB_PASS")

BROKER = f"http://{PINOT_HOST}:8099"
CONTROLLER = f"http://{PINOT_HOST.replace('broker', 'controller')}:9000"

def get_tables():

    try:

        r = requests.get(
            f"{CONTROLLER}/tables",
            timeout=10
        )

        data = r.json()

        return data.get("tables", [])

    except Exception as e:

        print("Error obteniendo tablas:", e)

        return []


def check_table_counts(tables):

    print(f"{'Tabla':<40} {'COUNT':>10}")

    print("-" * 55)

    for table in tables:

        try:

            r = requests.post(
                f"{BROKER}/query/sql",
                json={
                    "sql": f"SELECT COUNT(*) FROM {table}"
                },
                timeout=15
            )

            data = r.json()

            if "resultTable" in data:

                count = (
                    data["resultTable"]["rows"][0][0]
                )

            else:

                count = "ERROR"

        except Exception as e:

            count = str(e)[:20]

        print(
            f"{table:<40} {str(count):>10}"
        )


def check_segments(tables):

    print("\nSegmentos por tabla:\n")

    for table in tables:

        try:

            r = requests.get(
                f"{CONTROLLER}/segments/{table}",
                timeout=10
            )

            if r.status_code == 200:

                segs = r.json()

                offline = segs.get(
                    f"{table}_OFFLINE",
                    []
                )

                print(
                    f"{table:<40} "
                    f"{len(offline)} segmentos"
                )

        except Exception:

            print(f"{table:<40} error")


if __name__ == "__main__":

    tables = get_tables()

    check_table_counts(tables)

    check_segments(tables)

    print(
        "\nMonitoreo completado correctamente."
    )