from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime
from schemas.satellite import SatelliteResponse, SatelliteDetailResponse
from schemas.ephemeris import EphemerisResponse
from services.satellite_service import get_satellites, get_satellite_by_id
from services.ephemeris_service import build_ephemeris

router = APIRouter(prefix="/satellites", tags=["Satellites"])


@router.get("", response_model=list[SatelliteResponse])
def list_satellites(query: str = Query("", max_length=100),
                    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    term = query.strip().casefold()
    satellites = sorted(get_satellites(), key=lambda item: item.norad_id)
    matches = [item for item in satellites if not term or term in item.name.casefold()
               or term in str(item.norad_id)]
    return [SatelliteResponse(name=item.name, norad_id=item.norad_id)
            for item in matches[offset:offset + limit]]


def require_satellite(norad_id):
    satellite = get_satellite_by_id(norad_id)
    if satellite is None:
        raise HTTPException(404, "Satellite not found in the loaded catalog")
    return satellite


@router.get("/{norad_id}", response_model=SatelliteDetailResponse)
def satellite_detail(norad_id: int):
    satellite = require_satellite(norad_id)
    return SatelliteDetailResponse(name=satellite.name, norad_id=satellite.norad_id,
        epoch=satellite.epoch, inclination_deg=satellite.inclination_deg(),
        eccentricity=satellite.eccentricity, mean_motion_rev_day=satellite.mean_motion)


@router.get("/{norad_id}/ephemeris", response_model=EphemerisResponse)
def satellite_ephemeris(norad_id: int, start: AwareDatetime, end: AwareDatetime,
                         step_seconds: int = Query(60, ge=1, le=600)):
    satellite = require_satellite(norad_id)
    try:
        return build_ephemeris(satellite, start, end, step_seconds)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, "SGP4 could not propagate this object for the requested interval") from error
