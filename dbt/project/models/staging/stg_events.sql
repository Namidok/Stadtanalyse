WITH src AS (
    SELECT * FROM {{ source('silver', 'city_events') }}
)
SELECT
    event_id,
    name,
    category,
    lat,
    lon,
    start_time_utc,
    end_time_utc,
    expected_attendance,
    impact,
    impact_radius_km,
    status,
    event_ts,
    ingested_ts,
    dqr_valid
FROM src
WHERE dqr_valid IS TRUE
