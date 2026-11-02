"""
Versión de run_all.py que además sincroniza MySQL.
Puedes tomar el contenido y reemplazar tu run_all.py actual.
"""

import subprocess
from datetime import datetime
import sys

log_file = "log_estacion.txt"

def escribir_log(mensaje):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {mensaje}\n")

python_path = sys.executable

try:
    escribir_log("Inicio ejecución")

    subprocess.run([python_path, "poll_current.py"], check=True)
    escribir_log("poll_current OK")

    if datetime.now().hour == 0:
        subprocess.run([python_path, "backfill_rapid_1day.py"], check=True)
        escribir_log("backfill_rapid_1day OK")

    subprocess.run([python_path, "merge_csvs.py"], check=True)
    escribir_log("merge_csvs OK")

    subprocess.run([python_path, "sync_csv_to_mysql.py"], check=True)
    escribir_log("sync_csv_to_mysql OK")

    escribir_log("Fin ejecución")
    print("Proceso completado con MySQL")

except Exception as e:
    escribir_log(f"ERROR: {e}")
    raise
