{{ config(materialized='table') }}

WITH stop_segments AS (
    SELECT
        st.trip_id,
        st.stop_id,
        st.stop_sequence,
        s.stop_lat,
        s.stop_lon,
        LAG(s.stop_lat) OVER (PARTITION BY st.trip_id ORDER BY st.stop_sequence) AS prev_lat,
        LAG(s.stop_lon) OVER (PARTITION BY st.trip_id ORDER BY st.stop_sequence) AS prev_lon
    FROM {{ ref('dim_stop_times') }} st
    JOIN {{ ref('dim_stops') }} s USING (stop_id)
),
segments AS (
    SELECT
        trip_id,
        stop_id,
        stop_sequence,
        CASE
            WHEN prev_lat IS NULL THEN 0
            ELSE {{ haversine_km('prev_lat', 'prev_lon', 'stop_lat', 'stop_lon') }}
        END AS segment_km
    FROM stop_segments
),
weather_join AS (
    SELECT
        tu.trip_id,
        tu.stop_id,
        tu.event_ts,
        wh.zone_id AS weather_zone_id,
        wh.temperature_c,
        wh.precipitation_mm,
        wh.wind_speed_kmh,
        wh.humidity_pct,
        wh.condition
    FROM {{ ref('stg_trip_updates') }} tu
    JOIN {{ ref('dim_stops') }} s ON s.stop_id = tu.stop_id
    LEFT JOIN {{ ref('stg_weather_hourly') }} wh
        ON wh.zone_id = {{ weather_zone('s.stop_lat', 's.stop_lon') }}
       AND wh.obs_hour = date_trunc('hour', tu.event_ts)
),
events_impact AS (
    SELECT trip_id, stop_id, event_ts, event_proximity_km, nearest_impact
    FROM (
        SELECT
            tu.trip_id,
            tu.stop_id,
            tu.event_ts,
            {{ haversine_km('s.stop_lat', 's.stop_lon', 'e.lat', 'e.lon') }} AS event_proximity_km,
            e.impact AS nearest_impact,
            ROW_NUMBER() OVER (
                PARTITION BY tu.trip_id, tu.stop_id, tu.event_ts
                ORDER BY {{ haversine_km('s.stop_lat', 's.stop_lon', 'e.lat', 'e.lon') }}
            ) AS rn
        FROM {{ ref('stg_trip_updates') }} tu
        JOIN {{ ref('dim_stops') }} s ON s.stop_id = tu.stop_id
        CROSS JOIN {{ ref('stg_events') }} e
        WHERE e.status = 'ACTIVE'
          AND e.start_time_utc <= tu.event_ts
          AND e.end_time_utc >= tu.event_ts
    ) ranked
    WHERE rn = 1
),
route_stop_avg AS (
    SELECT
        route_id,
        stop_id,
        AVG(delay_seconds) AS historical_avg_delay
    FROM {{ ref('stg_trip_updates') }}
    GROUP BY 1, 2
)
SELECT
    tu.trip_id,
    tu.route_id,
    tu.vehicle_id,
    tu.stop_id,
    tu.stop_sequence,
    tu.delay_seconds,
    {{ delay_bucket('tu.delay_seconds') }} AS delay_bucket,
    tu.status,
    tu.event_ts,
    EXTRACT(HOUR FROM tu.event_ts)::int AS hour_of_day,
    EXTRACT(DOW FROM tu.event_ts)::int AS day_of_week,
    CASE WHEN EXTRACT(HOUR FROM tu.event_ts)::int IN (7, 8, 9, 17, 18, 19) THEN 1 ELSE 0 END AS is_rush_hour,
    r.route_mode,
    COALESCE(seg.segment_km, 0) AS segment_km,
    COALESCE(s.stop_zone_num, 0) AS stop_zone_num,
    COALESCE(w.weather_zone_id, 'unknown') AS weather_zone_id,
    w.temperature_c,
    w.precipitation_mm,
    w.wind_speed_kmh,
    w.humidity_pct,
    COALESCE(w.condition, 'unknown') AS condition,
    COALESCE(ei.event_proximity_km, 10.0) AS event_proximity_km,
    COALESCE(ei.nearest_impact, 0.0) AS nearest_event_impact,
    CASE WHEN ei.event_proximity_km IS NOT NULL THEN 1 ELSE 0 END AS event_nearby,
    COALESCE(rsa.historical_avg_delay, 0.0) AS historical_avg_delay,
    CURRENT_TIMESTAMP AS dbt_loaded_at
FROM {{ ref('stg_trip_updates') }} tu
LEFT JOIN {{ ref('dim_trips') }} t ON t.trip_id = tu.trip_id
LEFT JOIN {{ ref('dim_routes') }} r ON r.route_id = COALESCE(t.route_id, tu.route_id)
LEFT JOIN {{ ref('dim_stops') }} s ON s.stop_id = tu.stop_id
LEFT JOIN segments seg ON seg.trip_id = tu.trip_id AND seg.stop_id = tu.stop_id
LEFT JOIN weather_join w ON w.trip_id = tu.trip_id AND w.stop_id = tu.stop_id AND w.event_ts = tu.event_ts
LEFT JOIN events_impact ei ON ei.trip_id = tu.trip_id AND ei.stop_id = tu.stop_id AND ei.event_ts = tu.event_ts
LEFT JOIN route_stop_avg rsa ON rsa.route_id = tu.route_id AND rsa.stop_id = tu.stop_id
