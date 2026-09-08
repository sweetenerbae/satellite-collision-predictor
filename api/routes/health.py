from fastapi import APIRouter
from services.catalog_service import catalog
from services.screening_service import screening_service

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health():
    return {"status": "ok", "catalog": catalog.status(), "screening": screening_service.status()}
