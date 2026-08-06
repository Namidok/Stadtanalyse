-- Weather impact on delays: how conditions / precipitation move on-time rates.
SELECT
    condition,
    CASE
        WHEN precipitation_mm IS NULL THEN 'unknown'
        WHEN precipitation_mm = 0 THEN 'none'
        WHEN precipitation_mm < 2 THEN 'light'
        WHEN precipitation_mm < 6 THEN 'moderate'
        ELSE 'heavy'
    END AS precip_bucket,
    CASE
        WHEN temperature_c IS NULL THEN 'unknown'
        WHEN temperature_c < 0 THEN 'below_zero'
        WHEN temperature_c < 12 THEN 'cold'
        WHEN temperature_c < 22 THEN 'mild'
        ELSE 'warm'
    END AS temp_bucket,
    COUNT(*) AS observations,
    ROUND(AVG(delay_seconds)::numeric, 2) AS avg_delay_seconds,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delay_seconds)::numeric, 2) AS p95_delay_seconds,
    ROUND(100.0 * COUNT(*) FILTER (WHERE delay_bucket = 'on_time') / NULLIF(COUNT(*), 0), 2) AS on_time_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE delay_bucket = 'severe') / NULLIF(COUNT(*), 0), 2) AS severe_pct,
    CURRENT_TIMESTAMP AS dbt_loaded_at
FROM {{ ref('fct_trip_delays') }}
GROUP BY 1, 2, 3
