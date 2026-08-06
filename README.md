<p align="center">
  <img src="web/public/logo-wide.svg" alt="Stadtanalyse" width="620">
</p>

# Stadtanalyse — Smart Urban Mobility Data Lake & Analytics Platform

A production-style, end-to-end data engineering platform that ingests **real-time transit, weather, and city-event** data, cleanses and organizes it into a **Delta Lake medallion architecture**, runs **data-quality checks**, builds **analytical marts** with **dbt**, retrains an **XGBoost delay-prediction model**, and serves everything through a **FastAPI + React** dashboard — all orchestrated by **Airflow** and monitored with **Prometheus + Grafana**.

The platform runs in two modes:

- **Real data** (`make up-real`) — demo city **Berlin**. The real [gtfs.de](https://www.gtfs.de) national GTFS network plus **live GTFS-RT delays** from `realtime.gtfs.de` flow through Kafka → Bronze → Silver → quality → Gold → the XGBoost model. Vehicle *positions* are simulated on the real network (GTFS-RT exposes trip delays, not GPS positions); the UI labels the data source accordingly.
- **Fully synthetic** (`make up`) — self-contained demo with simulated network, positions, weather and events, plus the full Airflow cluster, no real feeds needed.

Everything runs locally with Docker Compose (no cloud credentials).

---

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        A[GTFS static feed] --> S[Transport Simulator]
        W[Weather Simulator] --> S
        E[City Events Simulator] --> S
    end

    S -- "4 Kafka topics" --> K[Apache Kafka]
    K --> SS[Spark Structured Streaming<br/>Bronze · Delta Lake]
    K --> B[Bronze Delta tables<br/>immutable raw]

    B --> SB[Spark batch<br/>Bronze → Silver]
    SB --> SL[Silver Delta + Parquet export]
    SL --> GE[Great Expectations<br/>quality suites]
    GE --> PG[(PostgreSQL<br/>silver + quality)]

    SL --> DBT[dbt · staging / gold]
    DBT --> G[(PostgreSQL<br/>gold marts)]
    G --> ML[XGBoost<br/>delay model]
    ML --> M[Model artifacts<br/>joblib + features]

    G --> API[FastAPI<br/>/api/v1]
    M --> API
    K --> API[FastAPI]
    API --> UI[React dashboard<br/>live map + charts + ML]

    AIR[Airflow DAG<br/>silver → quality → gold → retrain] -. triggers .-> SB
    AIR -. triggers .-> GE
    AIR -. triggers .-> DBT
    AIR -. triggers .-> ML

    P[Prometheus] --> API
    GRAF[Grafana] --> P
```

## Data flow (medallion architecture)

| Layer | Where | What |
|-------|-------|------|
| **Bronze** | Spark Structured Streaming → Delta Lake on MinIO | Immutable raw records from 4 Kafka topics: `raw.transport.vehicle.positions`, `raw.transport.trip.updates`, `raw.weather.observations`, `raw.city.events` |
| **Silver** | Spark batch ETL | Dedup, bounds/sanity filtering, type casting, `dqr_*` data-quality flags; exported to Delta + Parquet (MinIO) and loaded to PostgreSQL `silver` schema |
| **Quality** | Great Expectations | Versioned suites (one per table) run against the Silver exports; results published to `quality.quality_runs` |
| **Gold** | dbt | Raw GTFS views (`gold_silver` schema) → staging views → dims/facts → marts: `route_reliability`, `delay_trends`, `congestion_hotspots`, `weather_impact`, `events_impact`, `ml_features` |
| **Serve** | FastAPI + React | `/api/v1` reads gold marts (falls back to live-stream memory aggregations so the demo is never empty); the ML endpoint serves the trained model |

## Repository layout

```
├── ingest/               data simulators + Kafka producer (Docker)
│   ├── simulator/        transport / weather / city-events simulators
│   ├── realtime/         real GTFS + GTFS-RT download, extract & poller (real mode)
│   └── producer/         Kafka sink, run entrypoint
├── processing/spark/     Spark jobs + image (Delta Lake, S3A, JDBC)
├── quality/              Great Expectations suites + runner
├── dbt/                  dbt project (raw → staging → gold marts) + profiles
├── ml/                   XGBoost delay-model training + artifacts
├── api/                  FastAPI service (warehouse + live stream + ML)
├── web/                  React dashboard (Vite + Leaflet + Recharts)
├── airflow/dags/         batch-pipeline orchestration DAG (full mode only)
├── monitoring/           Prometheus config + Grafana provisioning
├── db/init/              PostgreSQL schema bootstrap
└── data/                 city profile, GTFS static feed, local DuckDB snapshot
```

## Quick start

### 0. Prerequisites
- Docker Desktop (macOS) with **at least 4 GB memory** allocated
- Python 3.11+ for the optional local-only path

### 1a. Real-data platform (recommended, demo Berlin)

```bash
cp .env.example .env        # optional, sensible defaults are baked in
make up-real                # builds & starts the real-data stack (no Airflow)
make jobs                   # once: GTFS static → silver → quality → gold → ml-train
```

`make up-real` starts Kafka, MinIO, Spark (streaming + jobs in `local[4]` mode),
PostgreSQL, the API and the web dashboard, plus the `realtime` service which
downloads the national GTFS feed, extracts the Berlin network, and polls the
live GTFS-RT delay feed every 10 seconds.

`make jobs` runs the batch pipeline **sequentially** (concurrent runs race):
1. **GTFS static load** — `load_gtfs_static.py` imports the real Berlin network
   (`stops` 15 000+, `stop_times` ~3.9 M, `routes`, `trips`) into Postgres `gtfs_raw`.
2. **Bronze → Silver** — Spark batch ETL on the live-ingested real records.
3. **Quality** — Great Expectations suites against the Silver exports.
4. **dbt** — builds `gold_silver` raw views → staging → Gold marts.
5. **ml-train** — trains the XGBoost delay model on `gold.ml_features` and saves
   artifacts to the `ml_artifacts` volume the API serves.

### 1b. Full platform (synthetic, with Airflow)

```bash
cp .env.example .env        # optional, sensible defaults are baked in
make up                     # builds & starts the whole stack
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Web dashboard | http://localhost:3000 | — |
| API docs (Swagger) | http://localhost:8000/docs | — |
| Airflow | http://localhost:8080 | admin / admin |
| Grafana | http://localhost:3001 | admin / admin |
| Kafka UI | http://localhost:8081 | — |
| MinIO console | http://localhost:9001 | stadtanalyse / stadtanalyse-secret |

### 2. Generate & inject demo data (synthetic mode only)

```bash
make seed     # generate GTFS feed + local DuckDB snapshot
make ingest   # start the simulators producing to Kafka (streaming)
```

Real mode needs no seeding — the `realtime` service downloads and installs the real feed on first start (data source badge on the dashboard shows **REAL GTFS + REALTIME DELAYS**).

### 3. Run the batch pipeline (once)

```bash
make jobs     # spark-run (silver) → quality (GE) → dbt (gold) → ml-train
```

Or trigger the equivalent DAG from Airflow (`stadtanalyse_batch_pipeline`, every 15 min).
The `spark-streaming` service continuously consumes Kafka into Bronze; the API streams live positions to the dashboard over Server-Sent Events.

### 4. Local-only development (no Docker)

```bash
python3 -m venv .venv
.venv/bin/pip install -r ml/requirements.txt -r api/requirements.txt \
  -r ingest/requirements.txt
make seed
make api-local              # http://localhost:8000
make web-local              # http://localhost:5173 (proxies /api to :8000)
```

Without Kafka/Postgres the API automatically seeds from the local DuckDB snapshot and serves live-stream analytics from memory — perfect for iterating on the UI or the model.

## Batch pipeline detail

`silver → quality → gold → retrain` is expressed as a Makefile target (`make jobs`) and, in the full synthetic mode, as an Airflow DAG (`airflow/dags/stadtanalyse_batch_pipeline.py`). In real mode the steps run sequentially via `docker compose --profile jobs run --rm`, and `spark-streaming` runs in `local[4]` mode (no cluster), continuously consuming Kafka into Bronze.

## ML: delay prediction

Trained on real GTFS-RT delays from the `gold.ml_features` table (via `processing/spark/scripts/run_train.sh` / `ml_train/train_delay_model.py`):

- **Regressor** — predicted delay in seconds (R² metric)
- **Classifier** — `on_time` / `delayed` / `severe` bucket with probabilities

Features include route mode, weather condition, rush-hour flag, segment length, event proximity, and historical average delay. The API serves both models at `POST /api/v1/ml/predict`; the dashboard includes a live prediction panel. Model artifacts live in the `ml_artifacts` volume, which the API mounts at `/opt/ml/model`.

## Observability

- **Prometheus** scrapes the API (`/metrics`: request rate, latency histograms, ingest counters), Kafka, Postgres, and node exporters.
- **Grafana** auto-provisions the **Stadtanalyse Platform** dashboard on first start.
- **Monitoring API**: `GET /api/v1/monitoring/pipeline` and `GET /api/v1/monitoring/quality` give a runtime view of ingestion, warehouse mode, and the last quality run.

## API surface (abridged)

`/api/v1/kpis` · `/api/v1/live/snapshot` · `/api/v1/live/positions/stream` (SSE) · `/api/v1/delays/{current,top-routes,trends}` · `/api/v1/hotspots` · `/api/v1/routes/reliability` · `/api/v1/weather/{current,impact}` · `/api/v1/events/{active,impact}` · `/api/v1/monitoring/{pipeline,quality}` · `/api/v1/ml/{info,predict}` · `/metrics`

## Possible extensions

- Extend real mode to more cities (Hamburg, München, … are already in `data/cities.json`; the GTFS loader + batch job take the city from `data/gtfs/.city`)
- Add GTFS-RT VehiclePosition support to real mode if a feed starts publishing GPS positions (currently GTFS-RT exposes only TripUpdates + ServiceAlerts)
- Deploy the same pipeline to a real cloud stack (Amazon MSK → EMR/Glue on S3 → Redshift) — the S3A/Delta/JDBC code paths are already cloud-ready
- Add `dbt` tests as hard gates in the Airflow DAG, or add a lineage UI (e.g. datahub/OpenLineage)
