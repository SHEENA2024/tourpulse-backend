"""
TourPulse FastAPI Backend
Run locally:  uvicorn app.main:app --reload --port 8000
Production:   uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import logging
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.model_loader import model_store
from app.db.database import init_db, SessionLocal
from app.api import forecast, mlops, admin, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Scheduler for periodic tasks ──────────────────────────────────────────────
scheduler = AsyncIOScheduler()


def _scheduled_drift_check():
    """Runs every 24 hours — compares recent inputs to training reference."""
    from app.services.drift import run_drift_check
    db = SessionLocal()
    try:
        result = run_drift_check(db)
        logger.info("Scheduled drift check: %s", result.get("status"))
    finally:
        db.close()


# ── Startup / Shutdown ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ────────────────────────────────────────────────────────────
    logger.info("🚀 TourPulse backend starting up...")

    # 1. Init database tables
    init_db()
    logger.info("✅ Database tables initialised")

    # 2. Load ML artifacts
    try:
        model_store.load()
    except FileNotFoundError as e:
        logger.error("❌ %s", e)
        logger.error(
            "Place your models/ folder (from Google Drive) next to this app "
            "and set MODELS_DIR in .env"
        )

    # 3. Schedule drift check (every 24 hours)
    scheduler.add_job(
        _scheduled_drift_check,
        trigger="interval",
        hours=24,
        id="drift_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("✅ Scheduler started (drift check every 24h)")

    yield

    # ── SHUTDOWN ───────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("👋 TourPulse backend shut down")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TourPulse API",
    description="MLOps-driven Tourism Demand Forecasting Platform — SDG 8",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(forecast.router)
app.include_router(mlops.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {
        "name":    "TourPulse API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/health",
        "status":  "running",
    }
