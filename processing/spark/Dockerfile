# CityPulse Spark worker image
# Spark 3.5.4 + Delta Lake 3.2.1 + Kafka + S3A/MinIO + PostgreSQL JDBC
FROM bitnamilegacy/spark:3.5.4

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
      xgboost==2.1.1 scikit-learn==1.5.2 pandas joblib duckdb==1.1.3

# Delta Lake, Spark-Kafka connector, MinIO/S3A and JDBC jars
RUN mkdir -p /opt/bitnami/spark/jars && \
    curl -fsSL -o /opt/bitnami/spark/jars/delta-spark_2.12-3.2.1.jar \
      https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.2.1/delta-spark_2.12-3.2.1.jar && \
    curl -fsSL -o /opt/bitnami/spark/jars/delta-storage-3.2.1.jar \
      https://repo1.maven.org/maven2/io/delta/delta-storage/3.2.1/delta-storage-3.2.1.jar && \
    curl -fsSL -o /opt/bitnami/spark/jars/spark-sql-kafka-0-10_2.12-3.5.4.jar \
      https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.4/spark-sql-kafka-0-10_2.12-3.5.4.jar && \
    curl -fsSL -o /opt/bitnami/spark/jars/kafka-clients-3.5.1.jar \
      https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.5.1/kafka-clients-3.5.1.jar && \
    curl -fsSL -o /opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar \
      https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -fsSL -o /opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.262.jar \
      https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    curl -fsSL -o /opt/bitnami/spark/jars/postgresql-42.7.3.jar \
      https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar && \
    chown -R 1001:1001 /opt/bitnami/spark/jars

# Spark job code + scripts
WORKDIR /opt/spark/work-dir
COPY processing/spark/jobs ./jobs
COPY processing/spark/scripts ./scripts
COPY ml/train ./ml_train
RUN chmod +x scripts/*.sh && chown -R 1001:1001 /opt/spark/work-dir

USER 1001

ENV PYTHONPATH=/opt/spark/work-dir
CMD ["/opt/bitnami/scripts/spark/run.sh"]
