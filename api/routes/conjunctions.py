from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Response
from schemas.conjunction import ConjunctionResponse, ScreeningStatusResponse, ConjunctionPage
from schemas.satellite import SatelliteResponse
from schemas.ephemeris import ConjunctionEphemerisResponse
from services.screening_service import screening_service
from services.snapshot_store import event_id
from services.ephemeris_service import build_ephemeris

router = APIRouter(prefix="/conjunctions", tags=["Conjunctions"])


def serialize(event, computed_at, snapshot_id=None):
    return ConjunctionResponse(id=event_id(event),
        satellite_1=SatelliteResponse(name=event.sat1.name, norad_id=event.sat1.norad_id),
        satellite_2=SatelliteResponse(name=event.sat2.name, norad_id=event.sat2.norad_id),
        miss_distance_km=event.distance_km, relative_velocity_km_s=event.relative_velocity_km_s,
        tca=event.tca, computed_at=computed_at, tca_location=event.tca_location,
        snapshot_id=snapshot_id)


def require_snapshot(id=None):
    snapshot = screening_service.get_snapshot(str(id) if id else None)
    if snapshot is None:
        if id:
            raise HTTPException(404, "Snapshot not found")
        raise HTTPException(503, "Initial screening has not completed; see /conjunctions/status")
    return snapshot


def require_event(id, snapshot_id=None):
    result = screening_service.resolve_event(id, str(snapshot_id) if snapshot_id else None)
    if result:
        return result
    if snapshot_id is None and screening_service.current_snapshot() is None:
        raise HTTPException(503, "Initial screening has not completed")
    raise HTTPException(404, "Event not found in the requested or retained snapshots")


@router.get("/status", response_model=ScreeningStatusResponse)
def screening_status():
    return screening_service.status()


@router.get("/page", response_model=ConjunctionPage)
def conjunction_page(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                     snapshot_id: Optional[UUID] = Query(None)):
    snapshot = require_snapshot(snapshot_id)
    next_offset = offset + limit if offset + limit < len(snapshot.events) else None
    return ConjunctionPage(snapshot_id=snapshot.id, computed_at=snapshot.computed_at,
        window_start=snapshot.window_start, window_end=snapshot.window_end,
        is_stale=snapshot.window_end < datetime.now(timezone.utc),
        total=len(snapshot.events), offset=offset, limit=limit, next_offset=next_offset,
        items=[serialize(event, snapshot.computed_at, snapshot.id)
               for event in snapshot.events[offset:offset + limit]])


@router.get("", response_model=list[ConjunctionResponse])
def list_conjunctions(response: Response, limit: int = Query(100, ge=1, le=500),
                      offset: int = Query(0, ge=0), snapshot_id: Optional[UUID] = Query(None)):
    snapshot = require_snapshot(snapshot_id)
    response.headers["X-Snapshot-ID"] = snapshot.id
    return [serialize(event, snapshot.computed_at, snapshot.id)
            for event in snapshot.events[offset:offset + limit]]


@router.get("/{id}", response_model=ConjunctionResponse)
def conjunction_detail(id: str, snapshot_id: Optional[UUID] = Query(None)):
    snapshot, event = require_event(id, snapshot_id)
    return serialize(event, snapshot.computed_at, snapshot.id)


@router.get("/{id}/ephemeris", response_model=ConjunctionEphemerisResponse)
def conjunction_ephemeris(id: str, seconds_before: int = Query(300, ge=1, le=1800),
                           seconds_after: int = Query(300, ge=1, le=1800),
                           step_seconds: int = Query(10, ge=1, le=600),
                           snapshot_id: Optional[UUID] = Query(None)):
    snapshot, event = require_event(id, snapshot_id)
    start = event.tca - timedelta(seconds=seconds_before)
    end = event.tca + timedelta(seconds=seconds_after)
    try:
        # Objects come from the chosen snapshot, including after a process restart.
        return ConjunctionEphemerisResponse(event_id=id, snapshot_id=snapshot.id,
            screening_computed_at=snapshot.computed_at, tca=event.tca,
            satellite_1=build_ephemeris(event.sat1, start, end, step_seconds, required_times=[event.tca]),
            satellite_2=build_ephemeris(event.sat2, start, end, step_seconds, required_times=[event.tca]))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, "SGP4 could not generate this encounter trajectory") from error
