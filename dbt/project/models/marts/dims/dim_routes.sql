SELECT
    route_id,
    route_short_name,
    route_long_name,
    route_mode,
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM {{ ref('gtfs_routes') }}
