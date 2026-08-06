#!/usr/bin/env bash
# Train the CityPulse delay-prediction model and persist artifacts.
set -euo pipefail

MASTER="${SPARK_MASTER_URL:-spark://spark-master:7077}"
echo ">>> CityPulse ML training (master=$MASTER)"
cd /opt/spark/work-dir

exec spark-submit \
  --master "$MASTER" \
  --deploy-mode client \
  --driver-memory "${SPARK_DRIVER_MEMORY:-2g}" \
  --executor-memory "${SPARK_EXECUTOR_MEMORY:-2g}" \
  --conf spark.hadoop.fs.s3a.endpoint="${S3_ENDPOINT:-http://minio:9000}" \
  --conf spark.hadoop.fs.s3a.access.key="${S3_ACCESS_KEY:-citypulse}" \
  --conf spark.hadoop.fs.s3a.secret.key="${S3_SECRET_KEY:-citypulse-secret}" \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  --conf spark.hadoop.fs.s3a.connection.ssl.enabled=false \
  --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
  --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog \
  jobs/train_delay_model.py --test-size 0.2
