-- Feature table consumed by the ML training job (XGBoost delay prediction).
SELECT
    trip_id,
    route_id,
    stop_id,
    delay_seconds,
    hour_of_day,
    day_of_week,
    is_rush_hour,
    route_mode,
    segment_km,
    stop_zone_num,
    temperature_c,
    precipitation_mm,
    wind_speed_kmh,
    humidity_pct,
    condition,
    event_proximity_km,
    event_nearby,
    historical_avg_delay,
    event_ts
FROM {{ ref('fct_trip_delays') }}
WHERE delay_seconds >= -120
