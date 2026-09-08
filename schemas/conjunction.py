from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel
from schemas.satellite import SatelliteResponse


class ConjunctionResponse(BaseModel):
    id: str
    satellite_1: SatelliteResponse
    satellite_2: SatelliteResponse
    miss_distance_km: float
    relative_velocity_km_s: float
    tca: datetime
    computed_at: Optional[datetime] = None


class ScreeningStatusResponse(BaseModel):
    state: Literal["pending", "running", "ready", "failed"]
    is_running: bool
    last_updated_at: Optional[datetime]
    last_error: Optional[str]
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    object_count: int
    event_count: int
