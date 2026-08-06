"""Shared Great Expectations helpers for suite generation and loading."""
from __future__ import annotations

import json
from pathlib import Path

import great_expectations as gx
import great_expectations.expectations.registry as registry


def build_expectation(expectation_type: str, kwargs: dict):
    """Instantiate a concrete expectation from its registered implementation."""
    cls = registry.get_expectation_impl(expectation_type)
    return cls(**kwargs)


def suite_from_dict(data: dict) -> gx.ExpectationSuite:
    expectations = [build_expectation(e["type"], e["kwargs"]) for e in data["expectations"]]
    return gx.ExpectationSuite(name=data.get("name", "unnamed"), expectations=expectations)


def load_suite(path: Path) -> gx.ExpectationSuite:
    return suite_from_dict(json.loads(Path(path).read_text()))


def save_suite(suite: gx.ExpectationSuite, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = suite.to_json_dict()
    payload["name"] = suite.name
    Path(path).write_text(json.dumps(payload, indent=2))
