from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.simulation_service import simulation_manager
    simulation_manager.start()
    yield
    simulation_manager.stop()
    from app.core.database import engine
    await engine.dispose()


app = FastAPI(
    title="ChargeEase — EV Fleet Intelligence Platform",
    description="Government EV Fleet Monitoring, Telemetry, and Public Data API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.operator import router as operator_router
from app.api.public import router as public_router
from app.api.ingest import router as ingest_router
from app.websocket.routes import router as ws_router
from app.api.charging_operator import router as charging_operator_router
from app.websocket.public_routes import router as ws_public_router

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(operator_router)
app.include_router(public_router)
app.include_router(ingest_router)
app.include_router(ws_router)
app.include_router(charging_operator_router)
app.include_router(ws_public_router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "chargeease-backend"}
