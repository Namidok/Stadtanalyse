from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..ml import model

router = APIRouter(prefix="/ml", tags=["ml"])


class PredictRequest(BaseModel):
    route_mode: str = Field("bus", description="rail | tram | bus")
    condition: str = Field("clear", description="weather condition")
    hour_of_day: int = Field(8, ge=0, le=23)
    day_of_week: int = Field(1, ge=0, le=6)
    is_rush_hour: int = Field(1, ge=0, le=1)
    segment_km: float = Field(0.8, ge=0)
    temperature_c: float = Field(15.0)
    precipitation_mm: float = Field(0.0, ge=0)
    wind_speed_kmh: float = Field(8.0, ge=0)
    event_proximity_km: float = Field(10.0, ge=0)
    event_nearby: int = Field(0, ge=0, le=1)
    historical_avg_delay: float = Field(30.0)
    stop_zone_num: int = Field(3, ge=0, le=5)


@router.get("/info")
def info():
    model.ensure_loaded()
    return model.info()


@router.post("/predict")
def predict(req: PredictRequest):
    return model.predict(req.model_dump())
