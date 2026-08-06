-- Business rule: reliability scores must stay within 0-100.
SELECT route_id, service_date, reliability_score
FROM {{ ref('mart_route_reliability') }}
WHERE reliability_score < 0 OR reliability_score > 100
