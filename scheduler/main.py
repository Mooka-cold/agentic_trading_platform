import os

import asyncio
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
from urllib.parse import quote_plus
from shared.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GlobalScheduler")

BACKEND_URL = settings.BACKEND_URL
AI_ENGINE_URL = settings.AI_ENGINE_URL
CRAWLER_URL = settings.CRAWLER_URL

async def trigger_task(service_name: str, url: str, method: str = "POST"):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "POST":
                resp = await client.post(url)
            elif method == "DELETE":
                resp = await client.delete(url)
            
            if resp.status_code in [200, 202]:
                logger.info(f"✅ Triggered {service_name}: {url}")
            else:
                logger.error(f"❌ Failed to trigger {service_name}: {resp.status_code} {resp.text}")
    except Exception as exc:
        logger.error(f"❌ Error triggering {service_name}: {exc}")

# --- Tasks ---

async def task_sync_1m():
    await trigger_task("Sync 1m", f"{CRAWLER_URL}/api/v1/sync/1m")

async def task_sync_1h():
    await trigger_task("Sync 1h", f"{CRAWLER_URL}/api/v1/sync/1h")

async def task_sync_1d():
    await trigger_task("Sync 1d", f"{CRAWLER_URL}/api/v1/sync/1d")

async def task_sync_news():
    await trigger_task("Sync News", f"{CRAWLER_URL}/api/v1/sync/news")

async def task_sync_rss():
    await trigger_task("Sync RSS", f"{CRAWLER_URL}/api/v1/sync/rss")

async def task_sync_newsapi():
    await trigger_task("Sync NewsAPI", f"{CRAWLER_URL}/api/v1/sync/newsapi")

async def task_sync_cryptopanic():
    await trigger_task("Sync CryptoPanic", f"{CRAWLER_URL}/api/v1/sync/cryptopanic")

async def task_sync_techflow():
    await trigger_task("Sync TechFlow", f"{CRAWLER_URL}/api/v1/sync/techflow")

async def task_monitor_positions():
    await trigger_task("Monitor Positions", f"{BACKEND_URL}/api/v1/jobs/monitor-positions")

async def task_periodic_review():
    # Trigger AI Engine's Reflector to check for pending reviews
    await trigger_task("AI Periodic Review", f"{AI_ENGINE_URL}/workflow/review")

async def task_cleanup_sessions():
    # Clean up FAILED sessions daily
    await trigger_task("Cleanup Sessions", f"{BACKEND_URL}/api/v1/workflow/sessions/cleanup", method="DELETE")

async def task_reset_daily_risk_metrics():
    await trigger_task("Reset Daily Risk Metrics", f"{BACKEND_URL}/api/v1/trade/risk/reset-daily")

async def task_sync_macro():
    # Call Crawler Service
    await trigger_task("Sync Macro Data", f"{CRAWLER_URL}/api/v1/trigger/macro", method="POST")

async def task_check_streamer():
    # Call Backend to ensure Streamer is running
    await trigger_task("Check Streamer", f"{BACKEND_URL}/api/v1/streamer/health", method="POST")

async def task_run_sentiment_interpreter():
    await trigger_task("Run Sentiment Interpreter", f"{AI_ENGINE_URL}/sentiment/interpreter/run")

async def task_run_llm_daily_calibration():
    symbol = quote_plus(settings.CALIBRATION_SYMBOL)
    window_days = settings.CALIBRATION_WINDOW_DAYS
    await trigger_task("Run LLM Daily Calibration", f"{BACKEND_URL}/api/v1/calibration/run?symbol={symbol}&window_days={window_days}")

# --- Main ---

async def task_cleanup_zombies():
    """
    Clean up zombie sessions (stale RUNNING) every 10 minutes.
    """
    # Use the same endpoint as cleanup_sessions but run it more frequently
    # backend endpoint now handles stale check
    try:
        url = f"{settings.BACKEND_URL}/api/v1/workflow/sessions/cleanup"
        async with httpx.AsyncClient(timeout=10.0) as client:
             resp = await client.delete(url)
             if resp.status_code == 200:
                 data = resp.json()
                 if data.get("marked_failed_count", 0) > 0:
                     logger.warning(f"🧟‍♂️ Cleaned up {data['marked_failed_count']} zombie sessions.")
    except Exception as e:
        logger.error(f"❌ Error cleaning zombies: {e}")

async def main():
    scheduler = AsyncIOScheduler()
    
    # 1. Market Data Sync
    scheduler.add_job(task_sync_1m, "interval", minutes=1, id="sync_1m")
    scheduler.add_job(task_sync_1h, "interval", hours=1, id="sync_1h")
    scheduler.add_job(task_sync_1d, "cron", hour=0, minute=5, id="sync_1d")
    
    # 2. News Sync
    scheduler.add_job(task_sync_rss, "interval", minutes=10, id="sync_rss")
    scheduler.add_job(task_sync_newsapi, "interval", minutes=10, id="sync_newsapi")
    scheduler.add_job(task_sync_cryptopanic, "interval", minutes=15, id="sync_cryptopanic")
    scheduler.add_job(task_sync_techflow, "interval", minutes=10, id="sync_techflow")
    scheduler.add_job(task_run_sentiment_interpreter, "interval", minutes=1, id="run_sentiment_interpreter")
    
    # 3. Risk Monitor (Guardian)
    scheduler.add_job(task_monitor_positions, "interval", minutes=1, id="monitor_positions")
    
    # 4. AI Periodic Review (Reflector)
    # Changed from 15 min to 5 min to catch missed reviews faster after restart
    scheduler.add_job(task_periodic_review, "interval", minutes=5, id="periodic_review")

    # 5. Macro Sync (Hourly)
    scheduler.add_job(task_sync_macro, "interval", hours=1, id="sync_macro")
    
    # 6. Maintenance
    scheduler.add_job(task_reset_daily_risk_metrics, "cron", hour=0, minute=0, id="reset_daily_risk_metrics")
    scheduler.add_job(task_cleanup_sessions, "cron", hour=3, minute=0, id="cleanup_sessions")
    scheduler.add_job(task_run_llm_daily_calibration, "cron", hour=0, minute=20, id="run_llm_daily_calibration")

    # 7. Streamer Health Check (Every 10s)
    # scheduler.add_job(task_check_streamer, "interval", seconds=10, id="check_streamer")

    # 8. Zombie Cleanup (Every 10m)
    scheduler.add_job(task_cleanup_zombies, "interval", minutes=10, id="cleanup_zombies")
    
    logger.info("🚀 Global Scheduler Started")
    scheduler.start()
    
    # Keep alive
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    asyncio.run(main())
