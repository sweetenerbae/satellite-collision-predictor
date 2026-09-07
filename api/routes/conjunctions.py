from fastapi import APIRouter, Query

from schemas.conjunction import (
    ConjunctionResponse,
    SatelliteResponse,
)
from services.conjunction_service import get_conjunctions


router = APIRouter(
    prefix="/conjunctions",
    tags=["Conjunctions"]
)


@router.get(
    "",
    response_model=list[ConjunctionResponse]
)
def list_conjunctions(
    threshold_km: float = Query(
        default=50.0,
        gt=0
    ),
    hours: int = Query(
        default=24,
        ge=1,
        le=168
    )
):
    events = get_conjunctions(
        threshold_km=threshold_km,
        hours=hours
    )

    return [
        ConjunctionResponse(
            satellite_1=SatelliteResponse(
                name=event.sat1.name,
                norad_id=event.sat1.norad_id
            ),
            satellite_2=SatelliteResponse(
                name=event.sat2.name,
                norad_id=event.sat2.norad_id
            ),
            miss_distance_km=event.distance_km,
            relative_velocity_km_s=event.relative_velocity_km_s,
            tca=event.tca
        )
        for event in events
    ]