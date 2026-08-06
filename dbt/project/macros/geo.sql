{% macro haversine_km(lat1, lon1, lat2, lon2) -%}
  2 * asin(
    sqrt(
      power(sin(radians(({{ lat2 }} - {{ lat1 }}) / 2.0)), 2)
      + cos(radians({{ lat1 }})) * cos(radians({{ lat2 }}))
      * power(sin(radians(({{ lon2 }} - {{ lon1 }}) / 2.0)), 2)
    )
  ) * 6371.0
{%- endmacro %}

{% macro weather_zone(lat, lon) -%}
  'Z'
  || (round(({{ lat }} - {{ var('city_lat') }}) / 0.03) + 2)::int::text
  || (round(({{ lon }} - {{ var('city_lon') }}) / 0.03) + 2)::int::text
{%- endmacro %}

{% macro delay_bucket(delay_seconds) -%}
  CASE
    WHEN {{ delay_seconds }} <= {{ var('on_time_threshold_seconds') }} THEN 'on_time'
    WHEN {{ delay_seconds }} <= {{ var('severe_delay_threshold_seconds') }} THEN 'delayed'
    ELSE 'severe'
  END
{%- endmacro %}
