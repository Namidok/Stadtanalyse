-- Delay trends aggregated hourly across the network.
SELECT
    DATE(event_ts) AS service_date,
    EXTRACT(HOUR FROM event_ts)::int AS hour_of_day,
    COUNT(*) AS observations,
    COUNT(DISTINCT trip_id) AS trips,
    ROUND(AVG(delay_seconds)::numeric, 2) AS avg_delay_seconds,
    ROUND(MAX(delay_seconds)::numeric, 2) AS max_delay_seconds,
    ROUND(100.0 * COUNT(*) FILTER (WHERE delay_bucket = 'on_time') / NULLIF(COUNT(*), 0), 2) AS on_time_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE delay_bucket = 'severe') / NULLIF(COUNT(*), 0), 2) AS severe_pct,
    ROUND(AVG(CASE WHEN is_rush_hour = 1 THEN delay_seconds END)::numeric, 2) AS avg_delay_rush_hour,
    CURRENT_TIMESTAMP AS dbt_loaded_at
FROM {{ ref('fct_trip_delays') }}
GROUP BY 1, 2
