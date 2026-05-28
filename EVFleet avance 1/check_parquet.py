import pyarrow.parquet as pq
import os

folder = "evfleet_parquet"
files = sorted([f for f in os.listdir(folder) if f.endswith(".parquet")])

print(f"{'Archivo':<35} {'Filas':>10} {'Cols':>6}")
print("-" * 55)
for f in files:
    t = pq.read_table(f"{folder}/{f}")
    print(f"{f:<35} {t.num_rows:>10,} {len(t.schema):>6}")
print(f"\nTotal archivos: {len(files)}")
