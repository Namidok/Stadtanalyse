#!/usr/bin/env bash
# Run a Spark job from the bundled jobs/ directory against the cluster.
# Usage: entrypoint.sh <job_name.py> [extra spark-submit args...]
set -euo pipefail

JOB="${1:?usage: entrypoint.sh <job.py>}"
shift
MASTER="${SPARK_MASTER_URL:-spark://spark-master:7077}"
DRIVER_MEM="${SPARK_DRIVER_MEMORY:-1g}"
EXEC_MEM="${SPARK_EXECUTOR_MEMORY:-1g}"

echo ">>> CityPulse Spark job: $JOB (master=$MASTER)"
cd /opt/spark/work-dir

exec spark-submit \
  --master "$MASTER" \
  --deploy-mode client \
  --driver-memory "$DRIVER_MEM" \
  --executor-memory "$EXEC_MEM" \
  --conf spark.hadoop.fs.s3a.endpoint="${S3_ENDPOINT:-http://minio:9000}" \
  --conf spark.hadoop.fs.s3a.access.key="${S3_ACCESS_KEY:-citypulse}" \
  --conf spark.hadoop.fs.s3a.secret.key="${S3_SECRET_KEY:-citypulse-secret}" \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  --conf spark.hadoop.fs.s3a.connection.ssl.enabled=false \
  --conf spark.delta.logStore.class=io.delta.storage.S3SingleDriverLogStore \
  --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
  --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog \
  jobs/"$JOB" "$@"
