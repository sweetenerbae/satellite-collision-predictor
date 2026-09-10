from fastapi import APIRouter, HTTPException, Query
from schemas.scene import OrbitalSceneResponse
from services.catalog_service import catalog
from services.orbital_scene_service import build_orbital_scene

router = APIRouter(prefix="/scene", tags=["Orbital Scene"])


@router.get("", response_model=OrbitalSceneResponse)
def orbital_scene(minutes: int = Query(100, ge=20, le=180),
                  step_seconds: int = Query(60, ge=10, le=300)):
    satellites = catalog.get_all()
    if not satellites:
        raise HTTPException(503, "Catalog is not ready")
    try:
        return build_orbital_scene(satellites, minutes=minutes, step_seconds=step_seconds)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(503, "SGP4 could not propagate the current catalog") from error
