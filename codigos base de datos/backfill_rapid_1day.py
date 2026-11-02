"""
Descarga el histórico rápido del último día de la estación PWS y lo guarda en CSV sin duplicados.

Uso:
    python backfill_rapid_1day.py
"""

import os
import requests
import pandas as pd

from config import API_KEY, STATION_ID, UNITS, RAPID_CSV_PATH

URL_RAPID_1DAY = "https://api.weather.com/v2/pws/observations/all/1day"


def flatten_observation(obs: dict) -> dict:
    metric = obs.get("metric", {}) or {}
    imperial = obs.get("imperial", {}) or {}
    block = metric if metric else imperial

    return {
        "stationID": obs.get("stationID"),
        "obsTimeUtc": obs.get("obsTimeUtc"),
        "obsTimeLocal": obs.get("obsTimeLocal"),
        "epoch": obs.get("epoch"),
        "lat": obs.get("lat"),
        "lon": obs.get("lon"),
        "neighborhood": obs.get("neighborhood"),
        "softwareType": obs.get("softwareType"),
        "country": obs.get("country"),
        "realtimeFrequency": obs.get("realtimeFrequency"),
        "temp": block.get("temp"),
        "heatIndex": block.get("heatIndex"),
        "dewpt": block.get("dewpt"),
        "windChill": block.get("windChill"),
        "windSpeed": block.get("windSpeed"),
        "windGust": block.get("windGust"),
        "pressure": block.get("pressure"),
        "precipRate": block.get("precipRate"),
        "precipTotal": block.get("precipTotal"),
        "elev": block.get("elev"),
        "humidity": obs.get("humidity"),
        "uv": obs.get("uv"),
        "solarRadiation": obs.get("solarRadiation"),
        "winddir": obs.get("winddir"),
        "qcStatus": obs.get("qcStatus"),
    }


def main():
    params = {
        "stationId": STATION_ID,
        "format": "json",
        "units": UNITS,
        "numericPrecision": "decimal",
        "apiKey": API_KEY,
    }

    respuesta = requests.get(URL_RAPID_1DAY, params=params, timeout=60)
    respuesta.raise_for_status()
    data = respuesta.json()

    observations = data.get("observations", [])
    if not observations:
        raise RuntimeError("La API no devolvió observaciones rápidas del último día.")

    df_nuevo = pd.DataFrame([flatten_observation(obs) for obs in observations])
    df_nuevo = df_nuevo.dropna(subset=["epoch"]).copy()
    df_nuevo["epoch"] = df_nuevo["epoch"].astype("int64")
    df_nuevo = df_nuevo.sort_values("epoch").drop_duplicates(subset=["stationID", "epoch"], keep="last")

    if os.path.exists(RAPID_CSV_PATH):
        df_existente = pd.read_csv(RAPID_CSV_PATH)
        if "epoch" in df_existente.columns:
            df_existente["epoch"] = pd.to_numeric(df_existente["epoch"], errors="coerce")
        df_total = pd.concat([df_existente, df_nuevo], ignore_index=True)
        df_total = df_total.drop_duplicates(subset=["stationID", "epoch"], keep="last").sort_values("epoch")
        df_total.to_csv(RAPID_CSV_PATH, index=False, encoding="utf-8")
    else:
        df_nuevo.to_csv(RAPID_CSV_PATH, index=False, encoding="utf-8")

    print(f"Observaciones procesadas: {len(df_nuevo)}")
    print(f"Archivo actualizado: {RAPID_CSV_PATH}")
    print(df_nuevo.head().to_string(index=False))


if __name__ == "__main__":
    main()
