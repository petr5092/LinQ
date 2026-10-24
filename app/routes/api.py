from fastapi import APIRouter
from app.routes.health import router as health_router
from app.routes.sites import router as sites_router
from app.routes.cameras import router as cameras_router
from app.routes.incidents import router as incidents_router
from app.routes.analytics import router as analytics_router
from app.routes.notifications import router as notifications_router
from app.routes.worker import router as worker_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(sites_router)
api_router.include_router(cameras_router)
api_router.include_router(incidents_router)
api_router.include_router(analytics_router)
api_router.include_router(notifications_router)
api_router.include_router(worker_router)
