{{ config(materialized='table') }}

SELECT
    tp.vehicle_id,
    tp.route_id,
    tp.route_mode,
    tp.trip_id,
    tp.stop_id,
    tp.lat,
    tp.lon,
    tp.speed_kmh,
    tp.heading_deg,
    tp.delay_seconds,
    {{ delay_bucket('tp.delay_seconds') }} AS delay_bucket,
    tp.congestion_level,
    tp.event_ts,
    CONCAT(ROUND(tp.lat::numeric, 2), '|', ROUND(tp.lon::numeric, 2)) AS grid_cell,
    ROUND(tp.lat::numeric, 2) AS cell_lat,
    ROUND(tp.lon::numeric, 2) AS cell_lon,
    wh.zone_id AS weather_zone_id,
    wh.condition,
    wh.precipitation_mm,
    wh.wind_speed_kmh
FROM {{ ref('stg_transport_positions') }} tp
LEFT JOIN {{ ref('stg_weather_hourly') }} wh
    ON wh.zone_id = {{ weather_zone('tp.lat', 'tp.lon') }}
   AND wh.obs_hour = date_trunc('hour', tp.event_ts)
