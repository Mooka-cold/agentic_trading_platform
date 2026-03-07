import os
import asyncio
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GlobalScheduler")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://ai-engine:8000")

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
    await trigger_task("Sync 1m", f"{BACKEND_URL}/api/v1/crawler/sync/1m")

async def task_sync_1h():
    await trigger_task("Sync 1h", f"{BACKEND_URL}/api/v1/crawler/sync/1h")

async def task_sync_1d():
    await trigger_task("Sync 1d", f"{BACKEND_URL}/api/v1/crawler/sync/1d")

async def task_sync_news():
    await trigger_task("Sync News", f"{BACKEND_URL}/api/v1/crawler/sync/news")

async def task_monitor_positions():
    await trigger_task("Monitor Positions", f"{BACKEND_URL}/api/v1/crawler/monitor")

async def task_periodic_review():
    # Trigger AI Engine's Reflector to check for pending reviews
    await trigger_task("AI Periodic Review", f"{AI_ENGINE_URL}/workflow/review/periodic")

async def task_cleanup_sessions():
    # Clean up FAILED sessions daily
    await trigger_task("Cleanup Sessions", f"{BACKEND_URL}/api/v1/workflow/sessions/cleanup", method="DELETE")

# --- Main ---

async def main():
    scheduler = AsyncIOScheduler()
    
    # 1. Market Data Sync
    scheduler.add_job(task_sync_1m, "interval", minutes=1, id="sync_1m")
    scheduler.add_job(task_sync_1h, "interval", hours=1, id="sync_1h")
    scheduler.add_job(task_sync_1d, "cron", hour=0, minute=5, id="sync_1d")
    
    # 2. News Sync
    scheduler.add_job(task_sync_news, "interval", minutes=15, id="sync_news")
    
    # 3. Risk Monitor (Guardian)
    scheduler.add_job(task_monitor_positions, "interval", minutes=1, id="monitor_positions")
    
    # 4. AI Periodic Review (Reflector)
    scheduler.add_job(task_periodic_review, "interval", minutes=15, id="periodic_review")
    
    # 5. Maintenance
    scheduler.add_job(task_cleanup_sessions, "cron", hour=3, minute=0, id="cleanup_sessions")

    logger.info("🚀 Global Scheduler Started")
    scheduler.start()
    
    # Keep alive
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    asyncio.run(main())
