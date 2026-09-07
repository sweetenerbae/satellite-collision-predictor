from pydantic import BaseModel


class SatelliteResponse(BaseModel):
    name: str
    norad_id: int

class SatelliteDetailResponse(SatelliteResponse):
    epoch: str
    inclination_deg: float
    eccentricity: float
    mean_motion_rev_day: float