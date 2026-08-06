FROM python:3.11-slim

WORKDIR /app

COPY ingest/requirements.txt ./ingest/requirements.txt
RUN pip install --no-cache-dir -r ingest/requirements.txt

COPY ingest ./ingest
COPY data ./data

ENV PYTHONPATH=/app
ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092

CMD ["python", "-m", "ingest.producer.run"]
