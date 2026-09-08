from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class StateSample(BaseModel):
    time: datetime
    position_km: tuple[float, float, float]
    velocity_km_s: tuple[float, float, float]


class EphemerisResponse(BaseModel):
    norad_id: int
    frame: Literal["TEME"] = "TEME"
    time_scale: Literal["UTC"] = "UTC"
    position_unit: Literal["km"] = "km"
    velocity_unit: Literal["km/s"] = "km/s"
    propagation_model: Literal["SGP4"] = "SGP4"
    element_epoch: str
    computed_at: datetime
    samples: list[StateSample]


class ConjunctionEphemerisResponse(BaseModel):
    event_id: str
    screening_computed_at: datetime
    tca: datetime
    satellite_1: EphemerisResponse
    satellite_2: EphemerisResponse
