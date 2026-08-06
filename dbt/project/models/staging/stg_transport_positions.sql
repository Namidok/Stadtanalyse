WITH src AS (
    SELECT * FROM {{ source('silver', 'transport_positions') }}
)
SELECT
    vehicle_id,
    route_id,
    route_mode,
    trip_id,
    direction_id,
    stop_id,
    next_stop_id,
    lat,
    lon,
    speed_kmh,
    heading_deg,
    delay_seconds,
    congestion_level,
    event_ts,
    ingested_ts,
    dqr_valid
FROM src
WHERE dqr_valid IS TRUE
