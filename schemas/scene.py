from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class SceneSample(BaseModel):
    time: datetime
    position_km: tuple[float, float, float]


class SceneObject(BaseModel):
    name: str
    norad_id: int
    samples: list[SceneSample]


class OrbitalSceneResponse(BaseModel):
    computed_at: datetime
    window_start: datetime
    window_end: datetime
    frame: Literal["TEME"] = "TEME"
    time_scale: Literal["UTC"] = "UTC"
    position_unit: Literal["km"] = "km"
    earth_equatorial_radius_km: float = 6378.137
    objects: list[SceneObject]
