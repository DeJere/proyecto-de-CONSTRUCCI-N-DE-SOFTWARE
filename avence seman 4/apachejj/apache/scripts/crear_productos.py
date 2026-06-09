from pocketbase import PocketBase
import requests
import os
from dotenv import load_dotenv

load_dotenv()

PB_URL = os.getenv("PB_URL", "http://127.0.0.1:8090")
PB_EMAIL = os.getenv("PB_EMAIL")
PB_PASS = os.getenv("PB_PASS")

pb = PocketBase(PB_URL)

# LOGIN
pb.admins.auth_with_password(
    PB_EMAIL,
    PB_PASS
)

print("LOGIN OK")

os.makedirs("downloads", exist_ok=True)

records = pb.collection("products").get_full_list()

print(f"PRODUCTOS: {len(records)}")

for product in records:

    print(f"\nBUSCANDO: {product.name}")

    # SI YA TIENE IMAGEN
    if hasattr(product, "image_status") and product.image_status:
        print("YA TIENE IMAGEN")
        continue

    try:

        # URL AUTOMÁTICA
        image_url = f"https://picsum.photos/400/400?random={product.id}"

        print("DESCARGANDO...")

        img_data = requests.get(image_url).content

        filename = f"downloads/{product.id}.jpg"

        with open(filename, "wb") as f:
            f.write(img_data)

        print("SUBIENDO A POCKETBASE...")

        with open(filename, "rb") as img:

            pb.collection("products").update(
                product.id,
                {
                    "image_status": True,
                    "image": img
                }
            )

        print("OK")

    except Exception as e:

        print("ERROR:")
        print(e)

print("\nTERMINADO")