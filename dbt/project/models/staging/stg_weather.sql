WITH src AS (
    SELECT * FROM {{ source('silver', 'weather_observations') }}
)
SELECT
    zone_id,
    lat,
    lon,
    temperature_c,
    feels_like_c,
    humidity_pct,
    wind_speed_kmh,
    precipitation_mm,
    condition,
    visibility_km,
    event_ts,
    ingested_ts,
    dqr_valid
FROM src
WHERE dqr_valid IS TRUE
