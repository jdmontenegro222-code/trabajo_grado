"""
Une el CSV de current polling y el CSV rapid 1day en un único archivo maestro.

Uso:
    python merge_csvs.py
"""

import os
import pandas as pd

from config import CSV_PATH, RAPID_CSV_PATH
print("Guardando en:", os.getcwd())
import os

ruta_script = os.path.dirname(os.path.abspath(__file__))
MASTER_PATH = os.path.join(ruta_script, "datos_estacion_master.csv")


def main():
    frames = []

    if os.path.exists(CSV_PATH):
        frames.append(pd.read_csv(CSV_PATH))

    if os.path.exists(RAPID_CSV_PATH):
        frames.append(pd.read_csv(RAPID_CSV_PATH))

    if not frames:
        raise RuntimeError("No existen archivos CSV para unir.")

    df = pd.concat(frames, ignore_index=True)

    if "epoch" in df.columns:
        df["epoch"] = pd.to_numeric(df["epoch"], errors="coerce")
        df = df.dropna(subset=["epoch"]).copy()
        df["epoch"] = df["epoch"].astype("int64")
        df = df.drop_duplicates(subset=["stationID", "epoch"], keep="last").sort_values("epoch")

    df.to_csv(MASTER_PATH, index=False, encoding="utf-8")
    print(f"Archivo maestro creado: {MASTER_PATH}")
    print(df.tail().to_string(index=False))


if __name__ == "__main__":
    main()
