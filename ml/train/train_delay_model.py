"""ML model training: predict public-transport delay.

Reads the `gold.ml_features` table (built by dbt from Silver trip updates,
weather and events), trains an XGBoost regressor for delay seconds and a
classifier for delay severity bucket, and persists:

  /opt/ml/model/model.joblib   - fitted pipeline (regressor + classifier)
  /opt/ml/model/features.json  - feature contract consumed by the API
  /opt/ml/model/metrics.json   - evaluation metrics, baselines + model metadata

Evaluation:
  * time-based split: rows sorted by event_ts, the last ~20% (cut on a
    timestamp boundary, so one poll never lands in both sets) is the test set
  * historical_avg_delay is recomputed point-in-time from the training window
    only (a row never sees its own delay or any test row)
  * MAE is compared against a training-mean and a route+stop-median baseline
  * the classifier reports macro-F1 and per-class recall, plus a
    majority-class baseline

Run (cluster):      spark-submit ... ml_train/train_delay_model.py
Run (local demo):   python train_delay_model.py --local [--local-db PATH]   (reads local DuckDB)
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
from sklearn.metrics import (  # noqa: E402
    accuracy_score, classification_report, f1_score, mean_absolute_error, r2_score, recall_score,
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
# Missing weather is filled with the training median (0 °C / 0 mm would be a fake reading).
WEATHER_FEATURES = ["temperature_c", "precipitation_mm", "wind_speed_kmh"]
TARGET_REGRESSION = "delay_seconds"
TARGET_CLASSIFICATION = "delay_bucket"

# model hyper-parameters (tuned for demo-scale data)
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


def load_data(local: bool, local_db: Path) -> pd.DataFrame:
    if local:
        import duckdb

        con = duckdb.connect(str(local_db))
        df = con.execute("""
            SELECT json_extract_string(record, '$.delay_seconds') AS delay_seconds,
                   json_extract_string(record, '$.route_mode') AS route_mode,
                   json_extract_string(record, '$.route_id') AS route_id,
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


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Clean types and add the class label. Weather NaNs are left for fill_weather()."""
    df = df.copy()
    df["delay_seconds"] = pd.to_numeric(df["delay_seconds"], errors="coerce")
    df["event_ts"] = pd.to_datetime(df["event_ts"], errors="coerce", utc=True)
    df = df.dropna(subset=["delay_seconds", "event_ts"])
    df = df[df["delay_seconds"] >= -120]  # drop implausible extreme earliness
    for col in ("route_id", "stop_id", "trip_id"):
        df[col] = df[col].fillna("").astype(str) if col in df.columns else ""
    for col in NUM_FEATURES:
        if col not in df.columns:
            df[col] = float("nan") if col in WEATHER_FEATURES else 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if col not in WEATHER_FEATURES:
            df[col] = df[col].fillna(0.0)
    for col in CAT_FEATURES:
        if col not in df.columns:
            df[col] = "unknown"
        df[col] = df[col].fillna("unknown").astype(str)
    df[TARGET_CLASSIFICATION] = df["delay_seconds"].apply(lambda d: BUCKET_MAP[bucket_delay(d)])
    return df


def time_split(df: pd.DataFrame, test_size: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Oldest rows train, newest rows test. The cut is moved to a timestamp
    boundary so rows sharing an event_ts (one GTFS-RT poll) stay together."""
    df = df.sort_values("event_ts", kind="stable").reset_index(drop=True)
    cutoff = df["event_ts"].iloc[int(len(df) * (1 - test_size))]
    train, test = df[df["event_ts"] < cutoff], df[df["event_ts"] >= cutoff]
    if train.empty or test.empty:
        raise ValueError(f"time split produced an empty set (cutoff={cutoff}); need more distinct timestamps")
    return train.copy(), test.copy()


def add_historical_avg_delay(train: pd.DataFrame, test: pd.DataFrame) -> None:
    """Recompute historical_avg_delay point-in-time, from the training window only.

    A training row sees the mean delay of its route+stop over training rows with
    a strictly earlier event_ts (never its own delay). A test row sees the mean
    over the whole training window, so test rows never contribute. Route+stop
    pairs with no earlier rows fall back to the global training mean.
    """
    keys = ["route_id", "stop_id"]
    y = TARGET_REGRESSION
    global_mean = train[y].mean()

    per_ts = train.groupby(keys + ["event_ts"])[y].agg(["sum", "count"]).sort_index()
    prior = per_ts.groupby(level=keys).cumsum() - per_ts  # strictly earlier timestamps
    prior_mean = (prior["sum"] / prior["count"].where(prior["count"] > 0)).rename("hist")
    train["historical_avg_delay"] = train.join(prior_mean, on=keys + ["event_ts"])["hist"].fillna(global_mean).values

    window_mean = train.groupby(keys)[y].mean().rename("hist")
    test["historical_avg_delay"] = test.join(window_mean, on=keys)["hist"].fillna(global_mean).values


def fill_weather(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    fill = {}
    for col in WEATHER_FEATURES:
        median = train[col].median()
        fill[col] = 0.0 if pd.isna(median) else float(median)
        train[col] = train[col].fillna(fill[col])
        test[col] = test[col].fillna(fill[col])
    return fill


def regression_baselines(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    y = TARGET_REGRESSION
    mean_pred = pd.Series(train[y].mean(), index=test.index)
    medians = train.groupby(["route_id", "stop_id"])[y].median().rename("med")
    rs_pred = test.join(medians, on=["route_id", "stop_id"])["med"].fillna(train[y].median())
    return {
        "train_mean": round(float(mean_absolute_error(test[y], mean_pred)), 2),
        "route_stop_median": round(float(mean_absolute_error(test[y], rs_pred)), 2),
    }


def classification_metrics(y_true: pd.Series, y_pred) -> dict:
    present = sorted(set(y_true) | set(y_pred))
    recalls = recall_score(y_true, y_pred, labels=list(BUCKET_NAMES), average=None, zero_division=0)
    in_test = set(y_true)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=present, average="macro", zero_division=0)), 4),
        # None = class absent from the test set (recall undefined)
        "recall_per_class": {BUCKET_NAMES[i]: (round(float(r), 4) if i in in_test else None)
                             for i, r in zip(BUCKET_NAMES, recalls)},
    }


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
    ap.add_argument("--local-db", type=Path, default=REPO_ROOT / "data/local/stadtanalyse.duckdb",
                    help="DuckDB file with a trip_updates(record JSON, event_ts) table (--local only)")
    ap.add_argument("--test-size", type=float, default=0.2)
    args = ap.parse_args()

    model_dir = Path(REPO_ROOT / "ml/model" if args.local else MODEL_DIR_ENV)
    print(f"Model artifacts -> {model_dir}")

    print("Loading data...")
    df = load_data(args.local, args.local_db)
    if len(df) < 200:
        print(f"Not enough rows ({len(df)}) to train a meaningful model.", file=sys.stderr)
        return 1

    df = prepare(df)
    train, test = time_split(df, args.test_size)
    add_historical_avg_delay(train, test)
    fill_values = fill_weather(train, test)
    X_train, X_test = train[CAT_FEATURES + NUM_FEATURES], test[CAT_FEATURES + NUM_FEATURES]

    # XGBClassifier needs labels 0..k-1, but a training window can miss a bucket
    # (e.g. no on_time rows). Encode the buckets present; features.json maps the
    # classifier's indices back to bucket names for the API.
    classes = sorted(train[TARGET_CLASSIFICATION].unique())
    encode = {c: i for i, c in enumerate(classes)}

    reg, clf = build_models()
    print(f"Training XGBoost on {len(X_train)} rows (test={len(X_test)})...")
    reg.fit(X_train, train[TARGET_REGRESSION])
    clf.fit(X_train, train[TARGET_CLASSIFICATION].map(encode))

    y_pred = reg.predict(X_test)
    clf_pred = [classes[i] for i in clf.predict(X_test)]
    mae = round(float(mean_absolute_error(test[TARGET_REGRESSION], y_pred)), 2)
    baselines = regression_baselines(train, test)
    majority = int(train[TARGET_CLASSIFICATION].mode()[0])
    metrics = {
        "regression": {
            "mae_seconds": mae,
            "baseline_mae": baselines,
            "beats_best_baseline": mae < min(baselines.values()),
            "r2": round(float(r2_score(test[TARGET_REGRESSION], y_pred)), 4),
        },
        "classification": {
            **classification_metrics(test[TARGET_CLASSIFICATION], clf_pred),
            "baseline_majority_class": {
                "predicts": BUCKET_NAMES[majority],
                **classification_metrics(test[TARGET_CLASSIFICATION], [majority] * len(test)),
            },
            "report": classification_report(test[TARGET_CLASSIFICATION], clf_pred, output_dict=True, zero_division=0),
        },
        "split": {
            "method": "time-based (sorted by event_ts, cut on a timestamp boundary)",
            "train_period_utc": [train["event_ts"].min().isoformat(), train["event_ts"].max().isoformat()],
            "test_period_utc": [test["event_ts"].min().isoformat(), test["event_ts"].max().isoformat()],
            "test_trips_also_in_train_pct": round(100 * float(test["trip_id"].isin(set(train["trip_id"])).mean()), 1),
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
                    "bucket_map": BUCKET_MAP,
                    "bucket_names": {i: BUCKET_NAMES[c] for i, c in enumerate(classes)},
                    "fill_values": fill_values}, indent=2)
    )
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print(f"Model saved to {model_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
