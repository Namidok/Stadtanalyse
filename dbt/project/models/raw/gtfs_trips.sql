SELECT
    trip_id,
    route_id,
    service_id,
    CAST(direction_id AS integer) AS direction_id,
    trip_headsign
FROM {{ source('gtfs_raw', 'gtfs_trips') }}
