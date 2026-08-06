FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    great-expectations==1.1.0 \
    pyarrow==17.0.0 \
    minio==7.2.9 \
    psycopg2-binary==2.9.10

COPY . .

ENTRYPOINT ["python", "run_quality.py"]
