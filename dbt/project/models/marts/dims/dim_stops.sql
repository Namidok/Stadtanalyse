SELECT
    stop_id,
    stop_name,
    stop_lat,
    stop_lon,
    stop_zone,
    CASE WHEN stop_zone RLIKE '^Z[0-9]+$' THEN TRY_CAST(REPLACE(stop_zone, 'Z', '') AS INT) ELSE NULL END AS stop_zone_num,
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM {{ ref('gtfs_stops') }}
