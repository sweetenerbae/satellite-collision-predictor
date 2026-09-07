from datetime import datetime

from pydantic import BaseModel
from schemas.satellite import SatelliteResponse

class ConjunctionResponse(BaseModel):
    satellite_1: SatelliteResponse
    satellite_2: SatelliteResponse

    miss_distance_km: float
    relative_velocity_km_s: float
    tca: datetime


