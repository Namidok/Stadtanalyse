SELECT
    route_id,
    route_short_name,
    route_long_name,
    route_mode
FROM {{ source('gtfs_raw', 'gtfs_routes') }}
