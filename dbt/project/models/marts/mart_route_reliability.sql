-- Route reliability per day: on-time %, average delay, p95, reliability score.
SELECT
    route_id,
    route_mode,
    DATE(event_ts) AS service_date,
    COUNT(*) AS stops_observed,
    COUNT(DISTINCT trip_id) AS trips,
    ROUND(AVG(delay_seconds)::numeric, 2) AS avg_delay_seconds,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delay_seconds)::numeric, 2) AS p95_delay_seconds,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delay_seconds)::numeric, 2) AS median_delay_seconds,
    ROUND(MAX(delay_seconds)::numeric, 2) AS max_delay_seconds,
    ROUND(100.0 * COUNT(*) FILTER (WHERE delay_bucket = 'on_time') / NULLIF(COUNT(*), 0), 2) AS on_time_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE delay_bucket = 'severe') / NULLIF(COUNT(*), 0), 2) AS severe_pct,
    ROUND(
        100.0 * (
            0.7 * COUNT(*) FILTER (WHERE delay_bucket = 'on_time')
            + 0.2 * COUNT(*) FILTER (WHERE delay_bucket = 'delayed')
        ) / NULLIF(COUNT(*), 0), 2
    ) AS reliability_score,
    CURRENT_TIMESTAMP AS dbt_loaded_at
FROM {{ ref('fct_trip_delays') }}
GROUP BY 1, 2, 3
