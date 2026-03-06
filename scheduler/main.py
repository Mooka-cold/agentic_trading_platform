import os
import asyncio
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://ai-engine:8000")
SYMBOLS = [s.strip() for s in os.getenv("SCHEDULE_SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT").split(",") if s.strip()]

async def post_json(url: str, payload: dict | None = None):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code, resp.text
    except Exception as exc:
        return 0, str(exc)

async def job_sync_1m():
    await post_json(f"{BACKEND_URL}/api/v1/jobs/sync-market", {"symbols": SYMBOLS, "timeframes": ["1m"]})

async def job_sync_1h():
    await post_json(f"{BACKEND_URL}/api/v1/jobs/sync-market", {"symbols": SYMBOLS, "timeframes": ["1h"]})

async def job_sync_1d():
    await post_json(f"{BACKEND_URL}/api/v1/jobs/sync-market", {"symbols": SYMBOLS, "timeframes": ["1d"]})

async def job_sync_news():
    await post_json(f"{BACKEND_URL}/api/v1/jobs/sync-news")

async def job_analyze():
    await post_json(f"{BACKEND_URL}/api/v1/jobs/analyze", {"symbols": SYMBOLS})

async def job_monitor_positions():
    await post_json(f"{BACKEND_URL}/api/v1/jobs/monitor-positions")

async def job_periodic_review():
    await post_json(f"{AI_ENGINE_URL}/workflow/review/periodic")

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(job_sync_1m, "interval", minutes=1, id="sync_1m")
    scheduler.add_job(job_sync_1h, "interval", hours=1, id="sync_1h")
    scheduler.add_job(job_sync_1d, "cron", hour=0, minute=5, id="sync_1d")
    scheduler.add_job(job_sync_news, "interval", minutes=15, id="sync_news")
    scheduler.add_job(job_analyze, "interval", minutes=15, jitter=120, id="analyze")
    scheduler.add_job(job_monitor_positions, "interval", minutes=1, id="monitor_positions")
    scheduler.add_job(job_periodic_review, "interval", minutes=30, id="periodic_review")
    scheduler.start()
    await asyncio.sleep(8)
    await asyncio.gather(job_sync_1m(), job_sync_news(), job_analyze())
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
