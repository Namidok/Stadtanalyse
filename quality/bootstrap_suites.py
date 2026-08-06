"""Great Expectations data-quality bootstrapping.

Defines the expectation suites for the Silver-layer tables and materialises
them as version-controlled JSON suites that `run_quality.py` executes.

Usage:
    python bootstrap_suites.py            # writes great_expectations/suites/*.json
"""
from __future__ import annotations

from pathlib import Path

from gx_utils import build_expectation, save_suite

HERE = Path(__file__).resolve().parent
SUITE_DIR = HERE / "great_expectations/suites"


def column_expectations() -> dict[str, list]:
    """Per-table expectations as (expectation_type, kwargs) tuples."""
    def not_null(column):
        return ("expect_column_values_to_not_be_null", {"column": column})

    def between(column, lo, hi):
        return ("expect_column_values_to_be_between", {"column": column, "min_value": lo, "max_value": hi})

    def in_set(column, values):
        return ("expect_column_values_to_be_in_set", {"column": column, "value_set": values})

    return {
        "transport_positions": [
            ("expect_table_columns_to_match_ordered_list",
             {"column_list": ["vehicle_id", "route_id", "route_mode", "trip_id",
                              "direction_id", "stop_id", "next_stop_id", "lat", "lon",
                              "speed_kmh", "heading_deg", "delay_seconds",
                              "congestion_level", "event_ts", "ingested_ts", "processed_ts"]}),
            not_null("vehicle_id"),
            not_null("route_id"),
            between("lat", -90.0, 90.0),
            between("lon", -180.0, 180.0),
            between("speed_kmh", 0.0, 150.0),
            between("delay_seconds", -120.0, 3600.0),
            ("expect_column_values_to_be_of_type", {"column": "lat", "type_": "float64"}),
        ],
        "trip_updates": [
            not_null("trip_id"),
            not_null("stop_id"),
            not_null("delay_seconds"),
            between("delay_seconds", -120.0, 3600.0),
            in_set("status", ["EARLY", "ON_TIME", "DELAYED"]),
        ],
        "weather_observations": [
            not_null("zone_id"),
            between("temperature_c", -50.0, 60.0),
            between("humidity_pct", 0.0, 100.0),
            in_set("condition", ["clear", "clouds", "rain", "snow", "fog", "storm", "sleet", "unknown"]),
        ],
        "city_events": [
            not_null("event_id"),
            between("lat", -90.0, 90.0),
            between("lon", -180.0, 180.0),
            in_set("status", ["ACTIVE", "ENDED"]),
        ],
    }


def main() -> int:
    from great_expectations import ExpectationSuite

    for table, definitions in column_expectations().items():
        expectations = [build_expectation(t, k) for t, k in definitions]
        suite = ExpectationSuite(name=table, expectations=expectations)
        out = SUITE_DIR / f"{table}.json"
        save_suite(suite, out)
        print(f"wrote {out.relative_to(HERE)} ({len(definitions)} expectations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
