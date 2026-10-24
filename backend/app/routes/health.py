"""Enhanced health endpoint.

GET /health          — liveness probe (always fast; no DB hit)
GET /health/ready    — readiness probe (checks DB connectivity)

Both return the same shape: {status, service, version}.
A readiness failure returns 503 SERVICE_UNAVAILABLE with the standard error shape.
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("verifai.health")

router = APIRouter(tags=["health"])

_VERSION = "0.1.0"


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — no dependencies checked. Always fast."""
    return {"status": "ok", "service": "verifai-api", "version": _VERSION}


@router.get("/health/ready")
def readiness(request: Request) -> JSONResponse:
    """Readiness probe — verifies the database is reachable.

    Kubernetes / load balancer: route traffic only when this returns 200.
    Returns 503 if the DB is not reachable so the instance is removed from rotation.
    """
    try:
        store = request.app.state.store
        # A lightweight no-op query — list 0 rows to confirm the connection is alive.
        store.list_opportunities(limit=0)
        return JSONResponse({"status": "ready", "service": "verifai-api", "version": _VERSION})
    except Exception:
        logger.exception("readiness check failed")
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "SERVICE_UNAVAILABLE",
                               "message": "Database is not reachable.",
                               "request_id": getattr(request.state, "request_id", "unknown")}},
        )