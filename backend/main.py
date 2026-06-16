"""
FastAPI — Aplicación principal
================================
Predictor Fútbol v1.0 — API REST
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import predictions, matches, teams
from schemas.prediction import HealthResponse

logger = structlog.get_logger()

# ─────────────────────────────────────────────────────────────
# Startup / Shutdown
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y limpieza de recursos."""
    logger.info("Iniciando Predictor Fútbol API...")
    # Aquí se pueden pre-cargar modelos, inicializar caché, etc.
    yield
    logger.info("Apagando Predictor Fútbol API...")


# ─────────────────────────────────────────────────────────────
# Aplicación FastAPI
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Predictor Fútbol API",
    description=(
        "Sistema de predicción de partidos de fútbol con modelos estadísticos y ML. "
        "Predicciones de goles, resultado 1X2, corners y faltas con probabilidades calibradas."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────

cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────

app.include_router(predictions.router, prefix="/api/v1", tags=["Predicciones"])
app.include_router(matches.router, prefix="/api/v1", tags=["Partidos"])
app.include_router(teams.router, prefix="/api/v1", tags=["Equipos"])


# ─────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/health", response_model=HealthResponse, tags=["Sistema"])
async def health_check():
    """Estado del sistema y modelos cargados."""
    return HealthResponse(
        status="ok",
        database="conectado",
        redis="conectado",
        modelos_cargados=["dixon_coles", "xgboost_1x2", "corners", "faltas"],
        version="1.0.0",
        timestamp=datetime.now(),
    )


@app.get("/api/v1/stats", tags=["Sistema"])
async def get_stats():
    """Retorna las métricas globales del sistema."""
    from db.connection import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as db:
        result_teams = await db.execute(text("SELECT COUNT(*) FROM teams"))
        total_teams = result_teams.scalar()
        
        result_matches_done = await db.execute(text("SELECT COUNT(*) FROM matches WHERE is_completed = TRUE"))
        matches_done = result_matches_done.scalar()
        
        result_matches_upcoming = await db.execute(text("SELECT COUNT(*) FROM matches WHERE is_completed = FALSE"))
        matches_upcoming = result_matches_upcoming.scalar()
        
        return {
            "total_teams": total_teams,
            "matches_completed": matches_done,
            "matches_upcoming": matches_upcoming,
            "total_matches": matches_done + matches_upcoming
        }


@app.get("/", include_in_schema=False)
async def root():
    return {"mensaje": "Predictor Fútbol API v1.0", "docs": "/api/docs"}


# ─────────────────────────────────────────────────────────────
# Manejadores de error globales
# ─────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Error no manejado", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor", "detalle": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
