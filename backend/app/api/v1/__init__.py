from fastapi import APIRouter
from app.api.v1.endpoints import market, news, signals, auth, trade, workflow, jobs, crawler

router = APIRouter()

# Include endpoints
router.include_router(market.router, prefix="/market", tags=["Market Data"])
router.include_router(news.router, prefix="/news", tags=["News"])
router.include_router(signals.router, prefix="/signals", tags=["AI Signals"])
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(trade.router, prefix="/trade", tags=["Trading"])
router.include_router(workflow.router, prefix="/workflow", tags=["Workflow Logs"])
router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
router.include_router(crawler.router, prefix="/crawler", tags=["Crawler"])
