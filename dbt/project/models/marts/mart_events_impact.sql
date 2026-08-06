-- Events impact: delay uplift by proximity to an active city event.
SELECT
    CASE
        WHEN event_proximity_km IS NULL THEN 'no_event'
        WHEN event_proximity_km < 1.0 THEN 'inside_1km'
        WHEN event_proximity_km < 2.0 THEN 'within_2km'
        WHEN event_proximity_km < 4.0 THEN 'within_4km'
        ELSE 'far'
    END AS proximity_bucket,
    COUNT(*) AS observations,
    ROUND(AVG(delay_seconds)::numeric, 2) AS avg_delay_seconds,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delay_seconds)::numeric, 2) AS p95_delay_seconds,
    ROUND(100.0 * COUNT(*) FILTER (WHERE delay_bucket = 'on_time') / NULLIF(COUNT(*), 0), 2) AS on_time_pct,
    ROUND(AVG(nearest_event_impact)::numeric, 3) AS avg_event_impact,
    CURRENT_TIMESTAMP AS dbt_loaded_at
FROM {{ ref('fct_trip_delays') }}
GROUP BY 1
