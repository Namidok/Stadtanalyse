WITH src AS (
    SELECT * FROM {{ source('silver', 'weather_observations') }}
)
SELECT
    zone_id,
    date_trunc('hour', event_ts) AS obs_hour,
    ROUND(AVG(temperature_c)::numeric, 2) AS temperature_c,
    ROUND(AVG(precipitation_mm)::numeric, 2) AS precipitation_mm,
    ROUND(MAX(precipitation_mm)::numeric, 2) AS max_precipitation_mm,
    ROUND(AVG(wind_speed_kmh)::numeric, 2) AS wind_speed_kmh,
    ROUND(AVG(humidity_pct)::numeric, 2) AS humidity_pct,
    (ARRAY_AGG(condition ORDER BY event_ts DESC))[1] AS condition,
    COUNT(*) AS obs_count
FROM src
WHERE dqr_valid IS TRUE
GROUP BY 1, 2
