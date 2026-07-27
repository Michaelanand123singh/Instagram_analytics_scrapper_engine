"""
FastAPI router for the Instagram analytics feature.

Wire this into your existing CRM FastAPI app:

    from instagram_router import router as instagram_router, get_instagram_service
    app.include_router(instagram_router)

`get_instagram_service` is a dependency you should override in your app to
supply your real Motor database instance — see the bottom of this file and
the accompanying README for the exact wiring.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from instagram_service import InstagramService

router = APIRouter(prefix="/instagram", tags=["instagram"])


class ConfigureRequest(BaseModel):
    sessionid: str


def get_instagram_service() -> InstagramService:
    """Override this dependency in your main app to inject your real DB.

    Example (in your app's startup / dependency wiring):

        from motor.motor_asyncio import AsyncIOMotorClient
        from instagram_router import get_instagram_service
        from instagram_service import InstagramService

        mongo_client = AsyncIOMotorClient(MONGO_URI)
        db = mongo_client["your_crm_db"]

        app.dependency_overrides[get_instagram_service] = lambda: InstagramService(db)
    """
    raise NotImplementedError(
        "Override get_instagram_service via app.dependency_overrides with your real DB."
    )


@router.get("/status")
async def status(service: InstagramService = Depends(get_instagram_service)):
    configured = await service.is_configured()
    latest = await service.get_latest_snapshot() if configured else None
    return {
        "configured": configured,
        "last_fetched_at": latest["fetched_at"] if latest else None,
    }


@router.post("/configure")
async def configure(
    payload: ConfigureRequest,
    service: InstagramService = Depends(get_instagram_service),
):
    try:
        return await service.configure_with_sessionid(payload.sessionid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deconfigure")
async def deconfigure(service: InstagramService = Depends(get_instagram_service)):
    await service.clear_configuration()
    return {"status": "ok", "detail": "Instagram configuration cleared."}


@router.post("/analytics/fetch")
async def fetch_analytics(
    amount: int = Query(30, ge=1, le=200),
    service: InstagramService = Depends(get_instagram_service),
):
    try:
        return await service.fetch_and_save_analytics(amount=amount)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analytics/latest")
async def latest_analytics(service: InstagramService = Depends(get_instagram_service)):
    snapshot = await service.get_latest_snapshot()
    if not snapshot:
        raise HTTPException(status_code=404, detail="No analytics snapshot saved yet.")
    return snapshot


@router.get("/analytics/history")
async def analytics_history(
    limit: int = Query(20, ge=1, le=100),
    service: InstagramService = Depends(get_instagram_service),
):
    return await service.get_snapshot_history(limit=limit)
