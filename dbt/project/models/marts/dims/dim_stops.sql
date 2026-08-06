SELECT
    stop_id,
    stop_name,
    stop_lat,
    stop_lon,
    stop_zone,
    CASE WHEN stop_zone ~ '^Z[0-9]+$' THEN REPLACE(stop_zone, 'Z', '')::int ELSE NULL END AS stop_zone_num,
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM {{ ref('gtfs_stops') }}
