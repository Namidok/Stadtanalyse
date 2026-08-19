-- Congestion hotspots: 100m-grid cells with slow speeds / high congestion.
SELECT
    grid_cell,
    cell_lat,
    cell_lon,
    COUNT(*) AS observations,
    COUNT(DISTINCT vehicle_id) AS vehicles,
    ROUND(AVG(speed_kmh)::numeric, 2) AS avg_speed_kmh,
    ROUND(AVG(congestion_level)::numeric, 3) AS avg_congestion,
    ROUND(AVG(delay_seconds)::numeric, 2) AS avg_delay_seconds,
    ROUND(100.0 * COUNT(CASE WHEN delay_bucket = 'severe' THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS severe_pct,
    {% if target.type == 'snowflake' %}
    COALESCE((ARRAY_AGG(condition) WITHIN GROUP (ORDER BY event_ts DESC))[0], 'unknown') AS condition,
{% else %}
    COALESCE((ARRAY_AGG(condition ORDER BY event_ts DESC))[1], 'unknown') AS condition,
{% endif %}
    ROW_NUMBER() OVER (ORDER BY AVG(delay_seconds) DESC) AS congestion_rank,
    CURRENT_TIMESTAMP AS dbt_loaded_at
FROM {{ ref('fct_vehicle_positions') }}
WHERE event_ts >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
GROUP BY 1, 2, 3
