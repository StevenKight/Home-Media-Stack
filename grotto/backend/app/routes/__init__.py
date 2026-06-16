"""
API Routes

Central route registration system. All sub-routers are combined into a single
root router that can be included in the FastAPI application.

Example:
    from fastapi import FastAPI
    from app.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
"""

from app.routes import auth
from fastapi import APIRouter

from app.routes import health
from app.routes import media

# Create root router and include all sub-routers
router = APIRouter()
router.include_router(auth.router)
router.include_router(health.router)
router.include_router(media.router)

__all__ = ["router"]
