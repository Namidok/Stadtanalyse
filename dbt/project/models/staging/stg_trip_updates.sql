WITH src AS (
    SELECT * FROM {{ source('silver', 'trip_updates') }}
)
SELECT
    trip_id,
    route_id,
    vehicle_id,
    stop_id,
    stop_sequence,
    scheduled_arrival_utc,
    actual_arrival_utc,
    delay_seconds,
    status,
    event_ts,
    ingested_ts,
    dqr_valid
FROM src
WHERE dqr_valid IS TRUE
