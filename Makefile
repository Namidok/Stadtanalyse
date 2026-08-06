.PHONY: help up down logs ps clean build api web quality dbt spark demo test lint seed validate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Full stack
# ---------------------------------------------------------------------------
up: ## Start the full platform (Kafka, MinIO, Postgres, Spark, API, Web, Airflow, Grafana)
	docker compose up -d --build
	@echo "\nStadtanalyse is starting..."
	@echo "  Web UI:        http://localhost:3000"
	@echo "  API docs:      http://localhost:8000/docs"
	@echo "  Grafana:       http://localhost:3001 (admin/admin)"
	@echo "  Airflow:       http://localhost:8080 (admin/admin)"
	@echo "  Kafka UI:      http://localhost:8081"
	@echo "  MinIO console: http://localhost:9001 (stadtanalyse/stadtanalyse-secret)"

up-lite: ## Start only the demo-facing services (Kafka, MinIO, Postgres, producer, API, Web)
	docker compose --profile ingest up -d --build kafka kafka-init minio minio-init postgres producer api web spark-streaming

up-real: ## Start the demo stack on REAL German transit data (gtfs.de GTFS + GTFS-RT delays)
	SIM_REAL_NETWORK=1 SIM_POSITIONS_ONLY=1 STADTANALYSE_DATA_SOURCE=real \
	docker compose --profile ingest --profile realtime up -d --build kafka kafka-init minio minio-init postgres producer realtime api web spark-streaming

jobs: ## Run batch pipeline once: GTFS static -> silver ETL -> quality -> gold (dbt) -> model
	@echo "== 1/5 GTFS static -> PostgreSQL =="
	docker compose --profile jobs run --rm --build spark-run /opt/spark/work-dir/scripts/entrypoint.sh load_gtfs_static.py
	@echo "== 2/5 Bronze -> Silver (Spark batch) =="
	docker compose --profile jobs run --rm spark-run
	@echo "== 3/5 Data quality (Great Expectations) =="
	docker compose --profile jobs run --rm --build quality
	@echo "== 4/5 dbt -> gold marts =="
	docker compose --profile jobs run --rm --build dbt
	@echo "== 5/5 Train delay model =="
	docker compose --profile jobs run --rm --build ml-train

seed: ## Generate GTFS static feed + local DuckDB demo snapshot
	.venv/bin/python scripts/gen_gtfs.py && .venv/bin/python -m ingest.producer.run --local

down: ## Stop everything
	docker compose down

clean: ## Stop everything and remove volumes (destroys data)
	docker compose down -v

logs: ## Follow logs
	docker compose logs -f --tail=100

ps: ## Show running services
	docker compose ps

# ---------------------------------------------------------------------------
# Individual services
# ---------------------------------------------------------------------------
ingest: ## Start the data simulators producing to Kafka
	docker compose --profile ingest up -d --build producer

build-api: ## Build API image
	docker compose build api

build-web: ## Build Web image
	docker compose build web

# ---------------------------------------------------------------------------
# Local (no Docker) development shortcuts
# ---------------------------------------------------------------------------
api-local: ## Run FastAPI locally (requires venv)
	cd api && uvicorn app.main:app --reload --port 8000

web-local: ## Run React dev server locally
	cd web && npm install && npm run dev

ml-local: ## Train the delay model locally on generated data
	python3 -m venv .venv && .venv/bin/pip install -q -r ml/requirements.txt && \
	.venv/bin/python -m ingest.producer.run --local && .venv/bin/python ml/train/train_delay_model.py --local

test: ## Run test suite
	.venv/bin/python -m pytest tests -v

validate: ## Validate compose config + dbt parse
	docker compose config --quiet
