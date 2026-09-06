from dataclasses import dataclass
from datetime import datetime

@dataclass
class ConjunctionEvent:
    sat1: object
    sat2: object
    distance_km: float
    relative_velocity_km_s: float
    tca: datetime