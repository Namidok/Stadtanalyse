SELECT
    route_id,
    agency_id,
    route_short_name,
    route_long_name,
    CAST(route_type AS integer) AS route_type,
    route_mode
FROM {{ source('gtfs_raw', 'gtfs_routes') }}
