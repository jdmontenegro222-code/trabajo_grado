"""
Descarga el dato actual de la estación PWS y lo guarda en CSV sin duplicados.

Uso:
    python poll_current.py
"""

import os
import requests
import pandas as pd

from config import API_KEY, STATION_ID, UNITS, CSV_PATH

URL_CURRENT = "https://api.weather.com/v2/pws/observations/current"


def main():
    params = {
        "stationId": STATION_ID,
        "format": "json",
        "units": UNITS,
        "numericPrecision": "decimal",
        "apiKey": API_KEY,
    }

    respuesta = requests.get(URL_CURRENT, params=params, timeout=30)
    respuesta.raise_for_status()
    data = respuesta.json()

    observations = data.get("observations", [])
    if not observations:
        raise RuntimeError("La API no devolvió observaciones.")

    obs = observations[0]
    metric = obs.get("metric", {}) or {}
    imperial = obs.get("imperial", {}) or {}
    block = metric if metric else imperial

    registro = {
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

    df_nuevo = pd.DataFrame([registro])

    if os.path.exists(CSV_PATH):
        df_existente = pd.read_csv(CSV_PATH)
        if "epoch" in df_existente.columns and registro["epoch"] in df_existente["epoch"].values:
            print("Dato repetido, no se guardó.")
        else:
            df_total = pd.concat([df_existente, df_nuevo], ignore_index=True)
            df_total.to_csv(CSV_PATH, index=False, encoding="utf-8")
            print(f"Dato nuevo guardado en {CSV_PATH}")
    else:
        df_nuevo.to_csv(CSV_PATH, index=False, encoding="utf-8")
        print(f"Archivo creado y dato guardado en {CSV_PATH}")

    print(df_nuevo.to_string(index=False))


if __name__ == "__main__":
    main()
