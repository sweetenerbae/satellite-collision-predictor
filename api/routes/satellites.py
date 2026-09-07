from fastapi import APIRouter

from schemas.satellite import SatelliteResponse
from services.satellite_service import get_satellites


router = APIRouter(
    prefix="/satellites",
    tags=["Satellites"]
)


@router.get(
    "",
    response_model=list[SatelliteResponse]
)
def list_satellites():
    satellites = get_satellites()

    return [
        SatelliteResponse(
            name=satellite.name,
            norad_id=satellite.norad_id
        )
        for satellite in satellites
    ]
