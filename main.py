import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes.health import router as health_router
from api.routes.conjunctions import router as conjunctions_router
from api.routes.satellites import router as satellites_router
from services.catalog_service import catalog
from services.snapshot_store import SnapshotStore
from services.screening_service import screening_service

logger = logging.getLogger(__name__)


async def update_loop():
    # A single sequential worker avoids overlapping catalog/screening jobs in this process.
    while True:
        try:
            await asyncio.to_thread(catalog.load)
            await asyncio.to_thread(screening_service.run_screening)
        except Exception:
            logger.exception("Background update failed; previous successful snapshots are retained")
        await asyncio.sleep(1800)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = os.environ.get("SATELLITE_DB_PATH") or str(Path(__file__).resolve().parent / "data/screening.sqlite3")
    await asyncio.to_thread(screening_service.configure_store, SnapshotStore(database))
    worker = asyncio.create_task(update_loop())
    try:
        yield  # Health and status are available while the initial calculation is running.
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


app = FastAPI(title="Satellite Close Approach API", version="0.2.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(conjunctions_router)
app.include_router(satellites_router)
