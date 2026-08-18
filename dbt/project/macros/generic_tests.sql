{% test greater_than_equal_zero(model, column_name) %}

SELECT {{ column_name }}
FROM {{ model }}
WHERE {{ column_name }} < 0

{% endtest %}
