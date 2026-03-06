from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from app.services.crawler.market import MarketCrawler
from app.services.crawler.news import NewsCrawler
from app.services.ai_client import run_analysis_cycle
from app.services.monitor import PositionMonitorService
from app.db.session import SessionLocalUser

router = APIRouter()

class MarketSyncRequest(BaseModel):
    symbols: Optional[List[str]] = None
    timeframes: Optional[List[str]] = None

class AnalyzeRequest(BaseModel):
    symbols: Optional[List[str]] = None

class MarketBackfillRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"
    hours: int = 24

@router.post("/sync-market")
async def sync_market(req: MarketSyncRequest):
    symbols = req.symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    timeframes = req.timeframes or ["1m"]
    crawler = MarketCrawler()
    try:
        await crawler.sync_market_data(symbols, timeframes)
    finally:
        await crawler.close()
    return {"status": "success", "symbols": symbols, "timeframes": timeframes}

@router.post("/sync-news")
async def sync_news():
    crawler = NewsCrawler()
    await crawler.sync_news()
    crawler.close()
    return {"status": "success"}

@router.post("/analyze")
async def analyze(req: AnalyzeRequest | None = Body(default=None)):
    symbols = (req.symbols if req else None) or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    await run_analysis_cycle(symbols)
    return {"status": "success", "symbols": symbols}

@router.post("/backfill-market")
async def backfill_market(req: MarketBackfillRequest):
    crawler = MarketCrawler()
    try:
        total = await crawler.backfill_ohlcv(req.symbol, req.timeframe, req.hours)
    finally:
        await crawler.close()
    return {"status": "success", "symbol": req.symbol, "timeframe": req.timeframe, "hours": req.hours, "inserted": total}

def _run_monitor_sync():
    db = SessionLocalUser()
    service = PositionMonitorService(db)
    try:
        service.check_and_manage_positions()
    finally:
        db.close()

@router.post("/monitor-positions")
async def monitor_positions():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_monitor_sync)
    return {"status": "success"}
