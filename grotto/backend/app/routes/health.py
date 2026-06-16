"""
health.py

Health check endpoints for monitoring API status and availability.

Endpoints:
    GET /health - Check if the API is running and healthy
"""

from fastapi import APIRouter

from app.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for API availability monitoring.

    Can be used for:
    - Load balancer health checks
    - Kubernetes/container orchestration liveness probes
    - Monitoring and alerting systems
    - Uptime verification

    Returns:
        JSON object with status "healthy" if API is running.
    """
    logger.info("Health check endpoint called")
    return {"status": "healthy"}
