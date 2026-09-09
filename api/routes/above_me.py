from fastapi import APIRouter, HTTPException, Query
from schemas.above_me import AboveMeResponse
from services.catalog_service import catalog
from services.above_me_service import objects_above_observer

router = APIRouter(prefix="/above-me", tags=["Above Me"])


@router.get("", response_model=AboveMeResponse)
def above_me(latitude_deg: float = Query(..., ge=-90, le=90),
             longitude_deg: float = Query(..., ge=-180, le=180)):
    satellites = catalog.get_all()
    if not satellites:
        raise HTTPException(503, "Catalog is not ready")
    try:
        return objects_above_observer(satellites, latitude_deg, longitude_deg)
    except RuntimeError as error:
        raise HTTPException(503, "SGP4 could not propagate the current catalog") from error
