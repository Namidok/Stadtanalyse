SELECT
    trip_id,
    stop_id,
    CAST(stop_sequence AS integer) AS stop_sequence,
    arrival_time,
    departure_time
FROM {{ source('gtfs_raw', 'gtfs_stop_times') }}
