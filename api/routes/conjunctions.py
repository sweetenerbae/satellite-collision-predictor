from uuid import uuid5, NAMESPACE_URL
from fastapi import APIRouter, HTTPException, Query
from schemas.conjunction import ConjunctionResponse, ScreeningStatusResponse
from schemas.satellite import SatelliteResponse
from schemas.ephemeris import ConjunctionEphemerisResponse
from services.screening_service import screening_service

router = APIRouter(prefix="/conjunctions", tags=["Conjunctions"])


def event_id(event):
    pair = sorted([event.sat1.norad_id, event.sat2.norad_id])
    return str(uuid5(NAMESPACE_URL, f"satellite:{pair[0]}:{pair[1]}:{event.tca.isoformat()}"))


def serialize(event, computed_at):
    return ConjunctionResponse(id=event_id(event),
        satellite_1=SatelliteResponse(name=event.sat1.name, norad_id=event.sat1.norad_id),
        satellite_2=SatelliteResponse(name=event.sat2.name, norad_id=event.sat2.norad_id),
        miss_distance_km=event.distance_km, relative_velocity_km_s=event.relative_velocity_km_s,
        tca=event.tca, computed_at=computed_at)


@router.get("/status", response_model=ScreeningStatusResponse)
def screening_status():
    return screening_service.status()


@router.get("", response_model=list[ConjunctionResponse])
def list_conjunctions(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    events, computed_at = screening_service.snapshot()
    if computed_at is None:
        raise HTTPException(503, "Initial screening has not completed; see /conjunctions/status")
    return [serialize(event, computed_at) for event in events[offset:offset + limit]]


@router.get("/{id}", response_model=ConjunctionResponse)
def conjunction_detail(id: str):
    events, computed_at = screening_service.snapshot()
    if computed_at is None:
        raise HTTPException(503, "Initial screening has not completed")
    for event in events:
        if event_id(event) == id:
            return serialize(event, computed_at)
    raise HTTPException(404, "Event not found in the current calculation snapshot")


@router.get("/{id}/ephemeris", response_model=ConjunctionEphemerisResponse)
def conjunction_ephemeris(id: str, seconds_before: int = Query(300, ge=1, le=1800),
                           seconds_after: int = Query(300, ge=1, le=1800),
                           step_seconds: int = Query(10, ge=1, le=600)):
    from datetime import timedelta
    from services.ephemeris_service import build_ephemeris
    events, computed_at = screening_service.snapshot()
    if computed_at is None:
        raise HTTPException(503, "Initial screening has not completed")
    event = next((event for event in events if event_id(event) == id), None)
    if event is None:
        raise HTTPException(404, "Event not found in the current calculation snapshot")
    start = event.tca - timedelta(seconds=seconds_before)
    end = event.tca + timedelta(seconds=seconds_after)
    try:
        # Keep the very Satellite instances used by this screening snapshot.
        # A catalog refresh must not silently change the event's orbital elements.
        return ConjunctionEphemerisResponse(event_id=id, screening_computed_at=computed_at,
            tca=event.tca, satellite_1=build_ephemeris(event.sat1, start, end, step_seconds, required_times=[event.tca]),
            satellite_2=build_ephemeris(event.sat2, start, end, step_seconds, required_times=[event.tca]))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, "SGP4 could not generate this encounter trajectory") from error
