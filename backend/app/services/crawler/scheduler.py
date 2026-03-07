from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.crawler.market import MarketCrawler
from app.services.crawler.news import NewsCrawler
from app.services.ai_client import run_analysis_cycle
from app.services.monitor import PositionMonitorService
from app.db.session import get_user_db
import asyncio

scheduler = AsyncIOScheduler()
market_crawler = MarketCrawler()
news_crawler = NewsCrawler()

from app.models.user import Strategy
from app.core.config import settings
import httpx

# Initialize with default, but will update from DB
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

def get_active_symbols():
    """Fetch active symbols from DB Strategies or Config"""
    # For now, we can fetch all unique symbols from active strategies
    # Or use a dedicated Watchlist table.
    # MVP: Stick to default list but allow extension via ENV or DB later.
    return SYMBOLS

async def job_sync_1m():
    symbols = get_active_symbols()
    print(f"⏰ [Scheduler] Triggering 1m sync for {len(symbols)} symbols...")
    await market_crawler.sync_market_data(symbols, ['1m'])

async def job_analyze():
    symbols = get_active_symbols()
    print(f"🧠 [Scheduler] Triggering AI Analysis for {len(symbols)} symbols...")
    await run_analysis_cycle(symbols)

async def job_sync_1h():
    symbols = get_active_symbols()
    print(f"⏰ [Scheduler] Triggering 1h sync for {len(symbols)} symbols...")
    await market_crawler.sync_market_data(symbols, ['1h'])

async def job_sync_1d():
    symbols = get_active_symbols()
    print(f"⏰ [Scheduler] Triggering 1d sync for {len(symbols)} symbols...")
    await market_crawler.sync_market_data(symbols, ['1d'])

async def job_sync_news():
    print("📰 [Scheduler] Triggering News sync...")
    await news_crawler.sync_news()

async def job_periodic_review():
    print("🧠 [Scheduler] Triggering Periodic Review (Reflector)...")
    try:
        async with httpx.AsyncClient() as client:
            # Call AI Engine API
            url = f"{settings.AI_ENGINE_URL}/workflow/review/periodic"
            resp = await client.post(url, timeout=10.0)
            if resp.status_code == 200:
                print("✅ [Scheduler] Review Triggered Successfully")
            else:
                print(f"⚠️ [Scheduler] Review Trigger Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"❌ [Scheduler] Review Connection Error: {e}")

def start_scheduler():
    # Run Periodic Review every 1 hour
    scheduler.add_job(job_periodic_review, 'interval', hours=1)

    # Sync 1m candles every minute
    scheduler.add_job(job_sync_1m, 'interval', minutes=1)
    
    # Sync 1h candles every hour
    scheduler.add_job(job_sync_1h, 'interval', hours=1)
    
    # Sync 1d candles every day at 00:05 UTC
    scheduler.add_job(job_sync_1d, 'cron', hour=0, minute=5)
    
    # Sync News every 15 minutes
    scheduler.add_job(job_sync_news, 'interval', minutes=15)
    
    # Run AI Analysis every 15 minutes (offset by 2 min to let data settle)
    scheduler.add_job(job_analyze, 'interval', minutes=15, jitter=120)
    
    # Guardian: Monitor Positions every 1 minute
    scheduler.add_job(job_monitor_positions, 'interval', minutes=1)

    scheduler.start()

def _run_monitor_sync():
    """Blocking function to run monitor"""
    db_gen = get_user_db()
    db = next(db_gen)
    try:
        service = PositionMonitorService(db)
        service.check_and_manage_positions()
    except Exception as e:
        print(f"Guardian Error: {e}")
    finally:
        db.close()

async def job_monitor_positions():
    print("🛡️ [Scheduler] Guardian Active: Checking positions...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_monitor_sync)
    print("🚀 Crawler Scheduler Started")
