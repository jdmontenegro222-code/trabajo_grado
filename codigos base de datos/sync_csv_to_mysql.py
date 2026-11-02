"""
Lee el archivo datos_estacion_master.csv y lo sincroniza con MySQL/MariaDB.
Crea la base de datos y la tabla si no existen.

Uso:
    python3 sync_csv_to_mysql.py
"""

from pathlib import Path
import pandas as pd
import pymysql

from db_config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, TABLE_NAME

BASE_DIR = Path(__file__).resolve().parent
MASTER_CSV = BASE_DIR / "datos_estacion_master.csv"


def to_none(value):
    if pd.isna(value):
        return None
    return value


def ensure_database_and_table():
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    finally:
        conn.close()

    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    stationID VARCHAR(50) NOT NULL,
                    obsTimeUtc DATETIME NULL,
                    obsTimeLocal DATETIME NULL,
                    epoch BIGINT NOT NULL,
                    lat DOUBLE NULL,
                    lon DOUBLE NULL,
                    neighborhood VARCHAR(255) NULL,
                    softwareType VARCHAR(255) NULL,
                    country VARCHAR(100) NULL,
                    realtimeFrequency VARCHAR(100) NULL,
                    temp DOUBLE NULL,
                    heatIndex DOUBLE NULL,
                    dewpt DOUBLE NULL,
                    windChill DOUBLE NULL,
                    windSpeed DOUBLE NULL,
                    windGust DOUBLE NULL,
                    pressure DOUBLE NULL,
                    precipRate DOUBLE NULL,
                    precipTotal DOUBLE NULL,
                    elev DOUBLE NULL,
                    humidity DOUBLE NULL,
                    uv DOUBLE NULL,
                    solarRadiation DOUBLE NULL,
                    winddir DOUBLE NULL,
                    qcStatus DOUBLE NULL,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_station_epoch (stationID, epoch),
                    KEY idx_obsTimeLocal (obsTimeLocal),
                    KEY idx_epoch (epoch)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
    finally:
        conn.close()


def load_master_csv():
    if not MASTER_CSV.exists():
        raise FileNotFoundError(f"No existe el archivo maestro: {MASTER_CSV}")

    df = pd.read_csv(MASTER_CSV)

    if df.empty:
        return df

    if "epoch" in df.columns:
        df["epoch"] = pd.to_numeric(df["epoch"], errors="coerce")
        df = df.dropna(subset=["epoch"]).copy()
        df["epoch"] = df["epoch"].astype("int64")

    for col in ["obsTimeUtc", "obsTimeLocal"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df = df.drop_duplicates(subset=["stationID", "epoch"], keep="last").sort_values("epoch").reset_index(drop=True)
    return df


def sync_dataframe_to_mysql(df):
    if df.empty:
        print("El CSV maestro está vacío. No hay datos para sincronizar.")
        return 0

    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True,
        charset="utf8mb4",
    )

    sql = f"""
        INSERT INTO `{TABLE_NAME}` (
            stationID, obsTimeUtc, obsTimeLocal, epoch, lat, lon, neighborhood,
            softwareType, country, realtimeFrequency, temp, heatIndex, dewpt,
            windChill, windSpeed, windGust, pressure, precipRate, precipTotal,
            elev, humidity, uv, solarRadiation, winddir, qcStatus
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            obsTimeUtc = VALUES(obsTimeUtc),
            obsTimeLocal = VALUES(obsTimeLocal),
            lat = VALUES(lat),
            lon = VALUES(lon),
            neighborhood = VALUES(neighborhood),
            softwareType = VALUES(softwareType),
            country = VALUES(country),
            realtimeFrequency = VALUES(realtimeFrequency),
            temp = VALUES(temp),
            heatIndex = VALUES(heatIndex),
            dewpt = VALUES(dewpt),
            windChill = VALUES(windChill),
            windSpeed = VALUES(windSpeed),
            windGust = VALUES(windGust),
            pressure = VALUES(pressure),
            precipRate = VALUES(precipRate),
            precipTotal = VALUES(precipTotal),
            elev = VALUES(elev),
            humidity = VALUES(humidity),
            uv = VALUES(uv),
            solarRadiation = VALUES(solarRadiation),
            winddir = VALUES(winddir),
            qcStatus = VALUES(qcStatus)
    """

    rows = []
    for _, row in df.iterrows():
        rows.append((
            to_none(row.get("stationID")),
            row.get("obsTimeUtc").to_pydatetime() if pd.notna(row.get("obsTimeUtc")) else None,
            row.get("obsTimeLocal").to_pydatetime() if pd.notna(row.get("obsTimeLocal")) else None,
            int(row.get("epoch")) if pd.notna(row.get("epoch")) else None,
            to_none(row.get("lat")),
            to_none(row.get("lon")),
            to_none(row.get("neighborhood")),
            to_none(row.get("softwareType")),
            to_none(row.get("country")),
            str(to_none(row.get("realtimeFrequency"))) if to_none(row.get("realtimeFrequency")) is not None else None,
            to_none(row.get("temp")),
            to_none(row.get("heatIndex")),
            to_none(row.get("dewpt")),
            to_none(row.get("windChill")),
            to_none(row.get("windSpeed")),
            to_none(row.get("windGust")),
            to_none(row.get("pressure")),
            to_none(row.get("precipRate")),
            to_none(row.get("precipTotal")),
            to_none(row.get("elev")),
            to_none(row.get("humidity")),
            to_none(row.get("uv")),
            to_none(row.get("solarRadiation")),
            to_none(row.get("winddir")),
            to_none(row.get("qcStatus")),
        ))

    try:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        print(f"Sincronización completada. Registros procesados: {len(rows)}")
        return len(rows)
    finally:
        conn.close()


def main():
    ensure_database_and_table()
    df = load_master_csv()
    print(f"Filas en CSV maestro: {len(df)}")
    sync_dataframe_to_mysql(df)
    print(f"Base: {DB_NAME} | Tabla: {TABLE_NAME}")


if __name__ == "__main__":
    main()
