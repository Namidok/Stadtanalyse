"""Great Expectations data-quality checks for the Silver layer.

Downloads the Parquet exports of the Silver tables from MinIO, runs the
versioned expectation suites against them and publishes a JSON validation
summary (printed + written to the artifacts bucket).

Usage:
    python run_quality.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import great_expectations as gx
import pandas as pd
import psycopg2
from minio import Minio

from gx_utils import load_suite

HERE = Path(__file__).resolve().parent
SUITE_DIR = HERE / "great_expectations/suites"

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://minio:9000").replace("http://", "").replace("https://", "")
S3_ACCESS = os.environ.get("S3_ACCESS_KEY", "citypulse")
S3_SECRET = os.environ.get("S3_SECRET_KEY", "citypulse-secret")
BUCKET = os.environ.get("S3_BUCKET_RAW", "warehouse")
PREFIX = "silver_export/"

TABLES = ["transport_positions", "trip_updates", "weather_observations", "city_events"]


def download_tables(client: Minio, tmp: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for table in TABLES:
        parts = []
        try:
            for obj in client.list_objects(BUCKET, prefix=f"{PREFIX}{table}/", recursive=True):
                if not obj.object_name.endswith(".parquet"):
                    continue
                local = tmp / obj.object_name.replace("/", "_")
                client.fget_object(BUCKET, obj.object_name, str(local))
                parts.append(local)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] could not fetch {table}: {e}", file=sys.stderr)
            continue
        if parts:
            frames[table] = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
            print(f"  {table}: {len(frames[table])} rows loaded")
    return frames


def validate_table(context, suite, df) -> dict:
    datasource = context.data_sources.add_or_update_pandas(name=f"quality_{suite.name}")
    asset = datasource.add_dataframe_asset(name="silver")
    batch_request = asset.build_batch_request(options={"dataframe": df})
    validator = context.get_validator(batch_request=batch_request, expectation_suite=suite)
    report = validator.validate()
    failed = [r.expectation_config.kwargs for r in report.results if not r.success]
    summary = {
        "table": suite.name,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "success": report.success,
        "expectations_passed": sum(1 for r in report.results if r.success),
        "expectations_total": len(report.results),
        "row_count": len(df),
        "failed_expectations": failed,
    }
    status = "PASS" if summary["success"] else "FAIL"
    print(f"  {suite.name}: {status} ({summary['expectations_passed']}/{summary['expectations_total']} expectations)")
    return summary


def publish_results(summaries: list[dict]) -> None:
    """Upsert validation summaries into Postgres (quality.quality_runs) so the
    API / pipeline monitoring endpoints can report on data quality."""
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "citypulse")
    password = os.environ.get("POSTGRES_PASSWORD", "citypulse-secret")
    db = os.environ.get("POSTGRES_DB", "citypulse")
    try:
        with psycopg2.connect(host=host, port=port, user=user, password=password, dbname=db, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                for s in summaries:
                    cur.execute(
                        """
                        INSERT INTO quality.quality_runs
                            (table_name, run_at_utc, success, expectations_passed, expectations_total, row_count)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (s["table"], s["run_at_utc"], s["success"], s["expectations_passed"],
                         s["expectations_total"], s["row_count"]),
                    )
            conn.commit()
        print(f"  published {len(summaries)} quality runs to Postgres")
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] could not publish quality results to Postgres: {e}", file=sys.stderr)


def main() -> int:
    client = Minio(S3_ENDPOINT, access_key=S3_ACCESS, secret_key=S3_SECRET, secure=False)
    context = gx.get_context(mode="ephemeral")
    tmp = Path(tempfile.mkdtemp(prefix="quality_"))
    try:
        frames = download_tables(client, tmp)
        if not frames:
            print("No Silver Parquet exports found in MinIO. Run the Spark batch job first.")
            return 2
        summaries = []
        for table in TABLES:
            if table not in frames:
                continue
            suite = load_suite(SUITE_DIR / f"{table}.json")
            summaries.append(validate_table(context, suite, frames[table]))

        payload = {
            "summary": summaries,
            "all_passed": all(s["success"] for s in summaries),
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(payload, indent=2))
        publish_results(summaries)
        return 0 if payload["all_passed"] else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
