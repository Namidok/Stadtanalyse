SELECT
    trip_id,
    route_id,
    service_id,
    direction_id,
    trip_headsign,
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM {{ ref('gtfs_trips') }}
