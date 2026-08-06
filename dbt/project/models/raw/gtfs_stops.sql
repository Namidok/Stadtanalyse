SELECT
    stop_id,
    stop_name,
    CAST(stop_lat AS double precision) AS stop_lat,
    CAST(stop_lon AS double precision) AS stop_lon,
    stop_zone
FROM {{ source('gtfs_raw', 'gtfs_stops') }}
