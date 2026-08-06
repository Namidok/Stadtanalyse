"""City selection for the simulated demo: which German city is being modeled.

Switching writes data/city.json, which the ingest producer watches. On the
next tick it regenerates the GTFS network for the new city and restarts its
simulators, streaming fresh data into the same Kafka topics.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import data_dir

router = APIRouter(prefix="/cities", tags=["cities"])

DEFAULT_CITY = {"name": "Berlin", "lat": 52.52, "lon": 13.405, "agency": "Stadtanalyse Transit"}


class CitySwitch(BaseModel):
    city: str


def _catalog() -> list[dict]:
    p = data_dir() / "cities.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except ValueError:
            pass
    return [DEFAULT_CITY]


def _current() -> dict:
    p = data_dir() / "city.json"
    if p.exists():
        try:
            data = json.loads(p.read_text())
            return {**DEFAULT_CITY, **data}
        except ValueError:
            pass
    return dict(DEFAULT_CITY)


@router.get("")
def list_cities() -> dict:
    """All switchable cities plus the currently active one."""
    return {"cities": _catalog(), "current": _current()["name"]}


@router.get("/current")
def current_city() -> dict:
    return _current()


@router.post("/switch")
def switch_city(payload: CitySwitch) -> dict:
    catalog = _catalog()
    match = next((c for c in catalog if c["name"] == payload.city), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Unknown city '{payload.city}'")
    profile = {**match, "agency": "Stadtanalyse Transit"}
    target = data_dir() / "city.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    tmp.replace(target)
    return {"ok": True, "city": profile}
