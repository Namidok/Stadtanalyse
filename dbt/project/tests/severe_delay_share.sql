-- Business rule: severe delays (>10 min) must stay a minority of observations.
SELECT route_id, service_date,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE delay_bucket = 'severe') AS severe
FROM {{ ref('fct_trip_delays') }}
GROUP BY 1, 2
HAVING COUNT(*) FILTER (WHERE delay_bucket = 'severe') > 0.35 * COUNT(*)
