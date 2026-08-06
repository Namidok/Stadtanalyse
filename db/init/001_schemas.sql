-- CityPulse serving database bootstrap.
-- Creates the schemas used by the medallion architecture:
--   silver  -> Spark cleansed layer (JDBC export) + dbt seeds
--   staging -> dbt staging views
--   gold    -> dbt marts consumed by the API
--   quality -> Great Expectations results published by the quality job

CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS quality;

-- Data-quality run ledger (populated by the Great Expectations job)
CREATE TABLE IF NOT EXISTS quality.quality_runs (
    id                   BIGSERIAL PRIMARY KEY,
    table_name           TEXT NOT NULL,
    run_at_utc           TIMESTAMPTZ NOT NULL DEFAULT now(),
    success              BOOLEAN NOT NULL,
    expectations_passed  INT NOT NULL DEFAULT 0,
    expectations_total   INT NOT NULL DEFAULT 0,
    row_count            BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_quality_runs_run_at ON quality.quality_runs (run_at_utc DESC);

-- Make the bootstrap user the owner everywhere.
GRANT ALL ON SCHEMA silver TO CURRENT_USER;
GRANT ALL ON SCHEMA staging TO CURRENT_USER;
GRANT ALL ON SCHEMA gold TO CURRENT_USER;
GRANT ALL ON SCHEMA quality TO CURRENT_USER;
ALTER TABLE quality.quality_runs OWNER TO CURRENT_USER;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA quality TO CURRENT_USER;
