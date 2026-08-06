SELECT
    trip_id,
    stop_id,
    stop_sequence,
    arrival_time,
    departure_time,
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM {{ ref('gtfs_stop_times') }}
