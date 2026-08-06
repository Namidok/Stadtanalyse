"""ML model training: predict public-transport delay.

Reads the `gold.ml_features` table (built by dbt from Silver trip updates,
weather and events), trains an XGBoost regressor for delay seconds and a
classifier for delay severity bucket, and persists:

  /opt/ml/model/model.joblib   - fitted pipeline (regressor + classifier)
  /opt/ml/model/features.json  - feature contract consumed by the API
  /opt/ml/model/metrics.json   - evaluation metrics + model metadata

Run (cluster):      spark-submit ... jobs/train_delay_model.py
Run (local demo):   python train_delay_model.py --local   (reads local DuckDB)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "processing/spark/jobs"))

import joblib  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score, classification_report, mean_absolute_error, r2_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402
from xgboost import XGBClassifier, XGBRegressor  # noqa: E402

MODEL_DIR_ENV = os.environ.get("ML_MODEL_DIR", "/opt/ml/model")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

CAT_FEATURES = ["route_mode", "condition", "day_of_week"]
NUM_FEATURES = [
    "hour_of_day", "is_rush_hour", "segment_km", "temperature_c",
    "precipitation_mm", "wind_speed_kmh", "event_proximity_km",
    "event_nearby", "historical_avg_delay", "stop_zone_num",
]
TARGET_REGRESSION = "delay_seconds"
TARGET_CLASSIFICATION = "delay_bucket"

# model hyper-parameters (tuned for demo-scale data; see ml/notebooks for tuning)
XGB_PARAMS = {
    "n_estimators": 300,
    "max_depth": 5,
    "learning_rate": 0.08,
    "subsample": 0.9,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1,
}


def bucket_delay(delay: float) -> str:
    if delay <= 120:
        return "on_time"
    if delay <= 600:
        return "delayed"
    return "severe"


BUCKET_MAP = {"on_time": 0, "delayed": 1, "severe": 2}
BUCKET_NAMES = {v: k for k, v in BUCKET_MAP.items()}


def load_data(local: bool) -> pd.DataFrame:
    if local:
        import duckdb

        db = Path(__file__).resolve().parent.parent.parent / "data/local/stadtanalyse.duckdb"
        con = duckdb.connect(str(db))
        df = con.execute("""
            SELECT json_extract_string(record, '$.delay_seconds') AS delay_seconds,
                   json_extract_string(record, '$.route_mode') AS route_mode,
                   json_extract_string(record, '$.stop_id') AS stop_id,
                   json_extract_string(record, '$.trip_id') AS trip_id,
                   event_ts
            FROM trip_updates
        """).fetchdf()
        con.close()
        # enrich with light features for the local demo path
        df["hour_of_day"] = pd.to_datetime(df["event_ts"]).dt.hour
        df["day_of_week"] = pd.to_datetime(df["event_ts"]).dt.dayofweek
        df["is_rush_hour"] = df["hour_of_day"].isin([7, 8, 9, 17, 18, 19]).astype(int)
        df["segment_km"] = 0.7
        df["temperature_c"] = 15.0
        df["precipitation_mm"] = 0.0
        df["wind_speed_kmh"] = 8.0
        df["condition"] = "clear"
        df["event_proximity_km"] = 10.0
        df["event_nearby"] = 0
        df["historical_avg_delay"] = df["delay_seconds"].astype(float).mean()
        df["stop_zone_num"] = df["stop_id"].str.split("_").str[0].map({"R": 1, "B": 2}).fillna(3).astype(int)
        return df

    from pyspark.sql import SparkSession

    from common import build_session, postgres_properties, postgres_url

    spark = build_session("stadtanalyse-ml-train")
    df_spark = (
        spark.read.jdbc(postgres_url(), "gold.ml_features", properties=postgres_properties())
        .limit(100000)
    )
    df = df_spark.toPandas()
    spark.stop()
    return df


def prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["delay_seconds"] = pd.to_numeric(df["delay_seconds"], errors="coerce")
    df = df.dropna(subset=["delay_seconds"])
    df = df[df["delay_seconds"] >= -120]  # drop implausible extreme earliness
    for col in NUM_FEATURES:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in CAT_FEATURES:
        if col not in df.columns:
            df[col] = "unknown"
        df[col] = df[col].fillna("unknown").astype(str)
    df[TARGET_CLASSIFICATION] = df["delay_seconds"].apply(lambda d: BUCKET_MAP[bucket_delay(d)])
    X = df[CAT_FEATURES + NUM_FEATURES]
    y_reg = df[TARGET_REGRESSION]
    y_clf = df[TARGET_CLASSIFICATION]
    return X, pd.DataFrame({"reg": y_reg, "clf": y_clf})


def build_models():
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
            ("num", StandardScaler(), NUM_FEATURES),
        ]
    )
    regressor = Pipeline([("pre", preprocessor), ("xgb", XGBRegressor(objective="reg:squarederror", **XGB_PARAMS))])
    classifier = Pipeline([("pre", preprocessor), ("xgb", XGBClassifier(**XGB_PARAMS))])
    return regressor, classifier


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="train on the local demo DuckDB")
    ap.add_argument("--test-size", type=float, default=0.2)
    args = ap.parse_args()

    model_dir = Path(REPO_ROOT / "ml/model" if args.local else MODEL_DIR_ENV)
    print(f"Model artifacts -> {model_dir}")

    print("Loading data...")
    df = load_data(args.local)
    if len(df) < 200:
        print(f"Not enough rows ({len(df)}) to train a meaningful model.", file=sys.stderr)
        return 1

    X, y = prepare(df)
    from sklearn.model_selection import train_test_split

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=args.test_size, random_state=42)

    reg, clf = build_models()
    print(f"Training XGBoost on {len(X_train)} rows (test={len(X_test)})...")
    reg.fit(X_train, y_train["reg"])
    clf.fit(X_train, y_train["clf"])

    y_pred = reg.predict(X_test)
    clf_pred = clf.predict(X_test)
    metrics = {
        "regression": {
            "mae_seconds": round(float(mean_absolute_error(y_test["reg"], y_pred)), 2),
            "r2": round(float(r2_score(y_test["reg"], y_pred)), 4),
        },
        "classification": {
            "accuracy": round(float(accuracy_score(y_test["clf"], clf_pred)), 4),
            "report": classification_report(y_test["clf"], clf_pred, output_dict=True),
        },
        "training_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "XGBoost",
        "params": XGB_PARAMS,
    }

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"regressor": reg, "classifier": clf}, model_dir / "model.joblib")
    (model_dir / "features.json").write_text(
        json.dumps({"cat_features": CAT_FEATURES, "num_features": NUM_FEATURES,
                    "target_regression": TARGET_REGRESSION,
                    "target_classification": TARGET_CLASSIFICATION,
                    "bucket_map": BUCKET_MAP, "bucket_names": BUCKET_NAMES}, indent=2)
    )
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print(f"Model saved to {model_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
