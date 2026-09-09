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
    snapshot_id: Optional[str] = None
    tca_location: Literal["interior", "window_start", "window_end"] = "interior"


class StationAlias(BaseModel):
    norad_id: int
    representative_norad_id: int
    reason: Literal["structural_module", "identical_elements"]


class ScreeningParameters(BaseModel):
    catalog_filter: Optional[str] = None
    screened_object_count: Optional[int] = None
    station_aliases: Optional[list[StationAlias]] = None
    algorithm: str
    threshold_km: float
    coarse_step_seconds: float
    refinement_step_seconds: float
    max_relative_velocity_km_s: float


class ScreeningStatusResponse(BaseModel):
    state: Literal["pending", "running", "ready", "failed"]
    is_running: bool
    last_updated_at: Optional[datetime]
    last_error: Optional[str]
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    object_count: int
    event_count: int
    parameters: Optional[ScreeningParameters] = None
    snapshot_id: Optional[str] = None
    is_stale: Optional[bool] = None


class ConjunctionPage(BaseModel):
    snapshot_id: str
    computed_at: datetime
    window_start: datetime
    window_end: datetime
    is_stale: bool
    total: int
    offset: int
    limit: int
    next_offset: Optional[int]
    items: list[ConjunctionResponse]
