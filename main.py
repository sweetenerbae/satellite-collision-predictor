from fastapi import FastAPI

from api.routes.health import router as health_router
from api.routes.conjunctions import router as conjunctions_router
from api.routes.satellites import router as satellites_router


app = FastAPI(
    title="Satellite Collision Predictor API",
    version="0.1.0"
)

app.include_router(health_router)
app.include_router(conjunctions_router)
app.include_router(satellites_router)