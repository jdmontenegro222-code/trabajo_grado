from flask import Flask, render_template
import pandas as pd
import pymysql
import joblib

from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

app = Flask(__name__)
REFRESH_SECONDS = 60
MODEL_PATH = "mejor_modelo_ml.pkl"


def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4"
    )


def get_data(limit=240):
    conn = get_connection()
    query = f'''
    SELECT obsTimeLocal, temp, humidity, pressure, windSpeed, solarRadiation
    FROM observaciones
    WHERE obsTimeLocal IS NOT NULL
 	 AND temp > 0
	 AND humidity > 0
	 AND pressure > 0
    ORDER BY obsTimeLocal DESC
    LIMIT {limit}
    '''
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return df

    df["obsTimeLocal"] = pd.to_datetime(df["obsTimeLocal"], errors="coerce")
    df = df.dropna(subset=["obsTimeLocal"]).sort_values("obsTimeLocal").reset_index(drop=True)
    return df


def build_features(df):
    df = df.copy()

    cols_num = ["temp", "humidity", "pressure", "windSpeed", "solarRadiation"]
    for col in cols_num:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["hour"] = df["obsTimeLocal"].dt.hour
    df["day"] = df["obsTimeLocal"].dt.day
    df["month"] = df["obsTimeLocal"].dt.month
    df["dayofweek"] = df["obsTimeLocal"].dt.dayofweek

    df["temp_lag1"] = df["temp"].shift(1)
    df["temp_lag2"] = df["temp"].shift(2)
    df["humidity_lag1"] = df["humidity"].shift(1)
    df["pressure_lag1"] = df["pressure"].shift(1)

    df = df.dropna().reset_index(drop=True)
    return df


def predict_future(df_feat, steps=12):
    model = joblib.load(MODEL_PATH)

    df_work = df_feat.copy()
    future_times = []
    future_preds = []

    if len(df_work) < 3:
        return future_times, future_preds

    delta = pd.Timedelta(minutes=5)
    base_time = df_feat["obsTimeLocal"].iloc[-1]

    for i in range(1, steps + 1):
        next_time = base_time + (i * delta)
        last = df_work.iloc[-1]

        x_pred = pd.DataFrame([{
            "humidity": last["humidity"],
            "pressure": last["pressure"],
            "windSpeed": last["windSpeed"],
            "solarRadiation": last["solarRadiation"],
            "hour": next_time.hour,
            "day": next_time.day,
            "month": next_time.month,
            "dayofweek": next_time.dayofweek,
            "temp_lag1": df_work.iloc[-1]["temp"],
            "temp_lag2": df_work.iloc[-2]["temp"],
            "humidity_lag1": df_work.iloc[-1]["humidity"],
            "pressure_lag1": df_work.iloc[-1]["pressure"]
        }])

        pred = float(model.predict(x_pred)[0])

        nueva_fila = {
            "obsTimeLocal": next_time,
            "temp": pred,
            "humidity": last["humidity"],
            "pressure": last["pressure"],
            "windSpeed": last["windSpeed"],
            "solarRadiation": last["solarRadiation"]
        }

        df_work = pd.concat([df_work, pd.DataFrame([nueva_fila])], ignore_index=True)

        future_times.append(next_time.strftime("%Y-%m-%d %H:%M:%S"))
        future_preds.append(round(pred, 3))

    return future_times, future_preds


def get_latest_predictions_with_real(limit=80):
    conn = get_connection()
    query = '''
    SELECT p.target_time, p.valor_predicho, p.valor_real, p.horizonte_minutos, p.created_at
    FROM predicciones p
    INNER JOIN (
        SELECT target_time, MAX(created_at) AS max_created_at
        FROM predicciones
        WHERE variable_objetivo = 'temp'
          AND valor_real IS NOT NULL
        GROUP BY target_time
    ) x
        ON p.target_time = x.target_time
       AND p.created_at = x.max_created_at
    WHERE p.variable_objetivo = 'temp'
      AND p.valor_real IS NOT NULL
    ORDER BY p.target_time DESC
    LIMIT %s
    '''
    df = pd.read_sql(query, conn, params=[limit])
    conn.close()

    if df.empty:
        return df

    df["target_time"] = pd.to_datetime(df["target_time"], errors="coerce")
    df = df.dropna(subset=["target_time"]).sort_values("target_time").reset_index(drop=True)
    return df


@app.route("/")
def index():
    df = get_data(limit=240)

    if df.empty:
        return "No hay datos disponibles en la base de datos."

    df_feat = build_features(df)

    if df_feat.empty:
        return "No hay suficientes datos para construir predicción."

    future_times, future_preds = predict_future(df_feat, steps=12)
    last_row = df_feat.iloc[-1]

    fechas_hist = df_feat["obsTimeLocal"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
    temp_hist = pd.to_numeric(df_feat["temp"], errors="coerce").fillna(0).tolist()
    hum = pd.to_numeric(df_feat["humidity"], errors="coerce").fillna(0).tolist()
    pres = pd.to_numeric(df_feat["pressure"], errors="coerce").fillna(0).tolist()
    wind = pd.to_numeric(df_feat["windSpeed"], errors="coerce").fillna(0).tolist()
    solar = pd.to_numeric(df_feat["solarRadiation"], errors="coerce").fillna(0).tolist()

    pred_line_labels = fechas_hist + future_times
    pred_line_real = temp_hist + [None] * len(future_preds)
    pred_line_pred = [None] * len(temp_hist) + future_preds

    df_eval = get_latest_predictions_with_real(limit=80)
    eval_labels = []
    eval_pred = []
    eval_real = []
    mae_eval = None
    rmse_eval = None

    if not df_eval.empty:
        eval_labels = df_eval["target_time"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
        eval_pred = pd.to_numeric(df_eval["valor_predicho"], errors="coerce").fillna(0).round(3).tolist()
        eval_real = pd.to_numeric(df_eval["valor_real"], errors="coerce").fillna(0).round(3).tolist()

        err = pd.to_numeric(df_eval["valor_real"], errors="coerce") - pd.to_numeric(df_eval["valor_predicho"], errors="coerce")
        mae_eval = round(float(err.abs().mean()), 4)
        rmse_eval = round(float((err.pow(2).mean()) ** 0.5), 4)

    return render_template(
        "index.html",
        refresh_seconds=REFRESH_SECONDS,
        fechas=fechas_hist,
        temp=temp_hist,
        hum=hum,
        pres=pres,
        wind=wind,
        solar=solar,
        pred_line_labels=pred_line_labels,
        pred_line_real=pred_line_real,
        pred_line_pred=pred_line_pred,
        eval_labels=eval_labels,
        eval_pred=eval_pred,
        eval_real=eval_real,
        mae_eval=mae_eval,
        rmse_eval=rmse_eval,
        last_time=str(last_row["obsTimeLocal"]),
        last_temp=round(float(last_row["temp"]), 3),
        last_hum=round(float(last_row["humidity"]), 3),
        last_pres=round(float(last_row["pressure"]), 3),
        last_wind=round(float(last_row["windSpeed"]), 3),
        last_solar=round(float(last_row["solarRadiation"]), 3) if pd.notna(last_row["solarRadiation"]) else 0,
        next_temp_pred=future_preds[0] if future_preds else None
    )


@app.route("/api/series_principales")
def series_principales():
    conn = get_connection()

    query = '''
    SELECT
        obsTimeLocal,
        temp,
        humidity,
        pressure,
        windSpeed,
        solarRadiation
    FROM observaciones
    WHERE obsTimeLocal IS NOT NULL
    ORDER BY obsTimeLocal DESC
    LIMIT 100
    '''

    df = pd.read_sql(query, conn)
    df = df.sort_values("obsTimeLocal")
    conn.close()

    if df.empty:
        return {
            "labels": [],
            "temp": [],
            "hum": [],
            "pres": [],
            "wind": [],
            "solar": []
        }

    df["obsTimeLocal"] = pd.to_datetime(df["obsTimeLocal"], errors="coerce")
    df = df.dropna(subset=["obsTimeLocal"]).copy()
    df["label"] = df["obsTimeLocal"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "labels": df["label"].tolist(),
        "temp": pd.to_numeric(df["temp"], errors="coerce").fillna(0).tolist(),
        "hum": pd.to_numeric(df["humidity"], errors="coerce").fillna(0).tolist(),
        "pres": pd.to_numeric(df["pressure"], errors="coerce").fillna(0).tolist(),
        "wind": pd.to_numeric(df["windSpeed"], errors="coerce").fillna(0).tolist(),
        "solar": pd.to_numeric(df["solarRadiation"], errors="coerce").fillna(0).tolist(),
    }


#######
@app.route("/api/real_vs_pred")
def real_vs_pred():
    conn = get_connection()

    query = """
    SELECT
        target_time,
        valor_real,
        valor_predicho,
        horizonte_minutos
    FROM predicciones
    WHERE valor_real IS NOT NULL
      AND horizonte_minutos = 5
    ORDER BY target_time DESC
    LIMIT 200
    """

    df = pd.read_sql(query, conn)
    conn.close()

    if not df.empty:
        df["target_time"] = pd.to_datetime(df["target_time"], errors="coerce")
        df = df.dropna(subset=["target_time"]).sort_values("target_time").reset_index(drop=True)

    return df.to_json(orient="records", date_format="iso")
##########
@app.route("/api/real_vs_pred_multi")
def real_vs_pred_multi():
    conn = get_connection()

    query = """
    SELECT
        p.target_time,
        p.horizonte_minutos,
        p.valor_predicho,
        p.valor_real,
        p.created_at
    FROM predicciones p
    INNER JOIN (
        SELECT
            target_time,
            horizonte_minutos,
            MAX(created_at) AS max_created_at
        FROM predicciones
        WHERE variable_objetivo = 'temp'
          AND valor_real IS NOT NULL
        GROUP BY target_time, horizonte_minutos
    ) x
      ON p.target_time = x.target_time
     AND p.horizonte_minutos = x.horizonte_minutos
     AND p.created_at = x.max_created_at
    WHERE p.variable_objetivo = 'temp'
      AND p.valor_real IS NOT NULL
    ORDER BY p.target_time DESC
    LIMIT 600
    """

    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return {
            "labels": [],
            "real": [],
            "pred_5": [],
            "pred_10": [],
            "pred_15": [],
            "pred_20": [],
            "pred_25": [],
            "pred_30": []
        }

    df["target_time"] = pd.to_datetime(df["target_time"], errors="coerce")
    df = df.dropna(subset=["target_time"]).sort_values("target_time").reset_index(drop=True)
    df["label"] = df["target_time"].dt.strftime("%Y-%m-%d %H:%M:%S")

    labels = sorted(df["label"].unique().tolist())

    real_map = df.groupby("label")["valor_real"].first().to_dict()

    pred_map = {}
    for horizonte in [5, 10, 15, 20, 25, 30]:
        sub = df[df["horizonte_minutos"] == horizonte].copy()
        pred_map[horizonte] = dict(
            zip(sub["label"], pd.to_numeric(sub["valor_predicho"], errors="coerce"))
        )

    return {
        "labels": labels,
        "real": [real_map.get(lbl, None) for lbl in labels],
        "pred_5":  [pred_map[5].get(lbl, None) for lbl in labels],
        "pred_10": [pred_map[10].get(lbl, None) for lbl in labels],
        "pred_15": [pred_map[15].get(lbl, None) for lbl in labels],
        "pred_20": [pred_map[20].get(lbl, None) for lbl in labels],
        "pred_25": [pred_map[25].get(lbl, None) for lbl in labels],
        "pred_30": [pred_map[30].get(lbl, None) for lbl in labels],
    }
############
@app.route("/test")
def test():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
