SELECT
    stop_id,
    stop_name,
    stop_lat,
    stop_lon,
    stop_zone,
{% if target.type == 'snowflake' %}
    CASE WHEN stop_zone RLIKE '^Z[0-9]+$' THEN TRY_CAST(REPLACE(stop_zone, 'Z', '') AS INT) ELSE NULL END AS stop_zone_num,
{% else %}
    CASE WHEN stop_zone ~ '^Z[0-9]+$' THEN REPLACE(stop_zone, 'Z', '')::int ELSE NULL END AS stop_zone_num,
{% endif %}
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM {{ ref('gtfs_stops') }}
