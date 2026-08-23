from fastapi import APIRouter

from app.api.v1.endpoints import ai, analytics_endpoints, auth, commerce, recovery, webhooks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(webhooks.router)
api_router.include_router(recovery.router)
api_router.include_router(analytics_endpoints.router)
api_router.include_router(commerce.router)
api_router.include_router(ai.router)


@api_router.get("/health", tags=["health"])
def health() -> dict:
    return {"success": True, "status": "ok", "service": "RecoveryAI API"}
