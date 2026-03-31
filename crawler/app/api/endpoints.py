from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from shared.db.session import get_user_db
from app.services.macro_crawler import MacroCrawlerService
from app.services.onchain_crawler import OnChainCrawlerService
from app.services.market_crawler import MarketCrawler
from app.services.news_crawler import NewsCrawler
from shared.core.symbols import get_default_symbol, get_schedule_symbols_from_env, get_schedule_timeframes_from_env

router = APIRouter()


def get_active_symbols() -> list[str]:
    return get_schedule_symbols_from_env()


class MarketBackfillRequest(BaseModel):
    symbol: str = get_default_symbol()
    timeframe: str = get_schedule_timeframes_from_env()[0]
    hours: int = 24

@router.post("/trigger/macro")
def trigger_macro_update(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_user_db)
):
    service = MacroCrawlerService(db)
    background_tasks.add_task(service.fetch_and_store_all)
    return {"status": "triggered"}

@router.post("/trigger/onchain")
def trigger_onchain_update(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_user_db)
):
    service = OnChainCrawlerService(db)
    background_tasks.add_task(service.fetch_and_store_all)
    return {"status": "triggered"}


@router.post("/sync/1m")
async def trigger_sync_1m(background_tasks: BackgroundTasks):
    async def _run():
        crawler = MarketCrawler()
        try:
            await crawler.sync_market_data(get_active_symbols(), ["1m"])
        finally:
            await crawler.close()
    background_tasks.add_task(_run)
    return {"status": "triggered", "task": "sync_1m"}


@router.post("/sync/1h")
async def trigger_sync_1h(background_tasks: BackgroundTasks):
    async def _run():
        crawler = MarketCrawler()
        try:
            await crawler.sync_market_data(get_active_symbols(), ["1h"])
        finally:
            await crawler.close()
    background_tasks.add_task(_run)
    return {"status": "triggered", "task": "sync_1h"}


@router.post("/sync/1d")
async def trigger_sync_1d(background_tasks: BackgroundTasks):
    async def _run():
        crawler = MarketCrawler()
        try:
            await crawler.sync_market_data(get_active_symbols(), ["1d"])
        finally:
            await crawler.close()
    background_tasks.add_task(_run)
    return {"status": "triggered", "task": "sync_1d"}


@router.post("/sync/news")
async def trigger_sync_news(background_tasks: BackgroundTasks):
    crawler = NewsCrawler()
    background_tasks.add_task(crawler.sync_news)
    return {"status": "triggered", "task": "sync_news"}


@router.post("/sync/rss")
async def trigger_sync_rss(background_tasks: BackgroundTasks):
    crawler = NewsCrawler()
    background_tasks.add_task(crawler.sync_rss)
    return {"status": "triggered", "task": "sync_rss"}


@router.post("/sync/newsapi")
async def trigger_sync_newsapi(background_tasks: BackgroundTasks):
    crawler = NewsCrawler()
    background_tasks.add_task(crawler.sync_newsapi)
    return {"status": "triggered", "task": "sync_newsapi"}


@router.post("/sync/cryptopanic")
async def trigger_sync_cryptopanic(background_tasks: BackgroundTasks):
    crawler = NewsCrawler()
    background_tasks.add_task(crawler.sync_cryptopanic)
    return {"status": "triggered", "task": "sync_cryptopanic"}


@router.post("/sync/techflow")
async def trigger_sync_techflow(background_tasks: BackgroundTasks):
    crawler = NewsCrawler()
    background_tasks.add_task(crawler.fetch_techflow_news)
    return {"status": "triggered", "task": "sync_techflow"}


@router.post("/sync/market")
async def sync_market(req: dict | None = None):
    symbols = (req or {}).get("symbols") or get_active_symbols()
    timeframes = (req or {}).get("timeframes") or get_schedule_timeframes_from_env()
    crawler = MarketCrawler()
    try:
        await crawler.sync_market_data(symbols, timeframes)
    finally:
        await crawler.close()
    return {"status": "success", "symbols": symbols, "timeframes": timeframes}


@router.post("/sync/backfill")
async def backfill_market(req: MarketBackfillRequest):
    crawler = MarketCrawler()
    try:
        total = await crawler.backfill_ohlcv(req.symbol, req.timeframe, req.hours)
    finally:
        await crawler.close()
    return {"status": "success", "symbol": req.symbol, "timeframe": req.timeframe, "hours": req.hours, "inserted": total}
