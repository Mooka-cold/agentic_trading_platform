from fastapi import APIRouter
from app.api.v1.endpoints import market, news, trade

router = APIRouter()
router.include_router(market.router, prefix="/market", tags=["Market Data"])
router.include_router(news.router, prefix="/news", tags=["News Intelligence"])
router.include_router(trade.router, prefix="/trade", tags=["Trading Execution"])
