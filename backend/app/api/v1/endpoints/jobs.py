from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import httpx

from app.services.ai_client import run_analysis_cycle
from app.services.monitor import PositionMonitorService
from app.db.session import SessionLocalUser
from app.core.config import settings
from shared.core.symbols import get_schedule_symbols_from_env

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
    symbols = req.symbols or get_schedule_symbols_from_env()
    timeframes = req.timeframes or ["1m"]
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.CRAWLER_URL}/api/v1/sync/market",
            json={"symbols": symbols, "timeframes": timeframes},
        )
        response.raise_for_status()
    return {"status": "success", "symbols": symbols, "timeframes": timeframes}

@router.post("/sync-news")
async def sync_news():
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{settings.CRAWLER_URL}/api/v1/sync/news")
        response.raise_for_status()
    return {"status": "success"}

@router.post("/analyze")
async def analyze(req: AnalyzeRequest | None = Body(default=None)):
    symbols = (req.symbols if req else None) or get_schedule_symbols_from_env()
    await run_analysis_cycle(symbols)
    return {"status": "success", "symbols": symbols}

@router.post("/backfill-market")
async def backfill_market(req: MarketBackfillRequest):
    async with httpx.AsyncClient(timeout=40.0) as client:
        response = await client.post(
            f"{settings.CRAWLER_URL}/api/v1/sync/backfill",
            json=req.model_dump(),
        )
        response.raise_for_status()
        total = (response.json() or {}).get("inserted", 0)
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
