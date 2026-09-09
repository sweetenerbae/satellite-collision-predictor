from datetime import datetime
from pydantic import BaseModel


class AboveMeObject(BaseModel):
    name: str
    norad_id: int
    azimuth_deg: float
    elevation_deg: float
    range_km: float


class AboveMeResponse(BaseModel):
    computed_at: datetime
    observer_latitude_deg: float
    observer_longitude_deg: float
    reference_frame: str = "TEME"
    transformation_model: str = "GMST_APPROX"
    objects: list[AboveMeObject]
