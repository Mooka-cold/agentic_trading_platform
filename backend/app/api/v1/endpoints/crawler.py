from fastapi import APIRouter, BackgroundTasks
from app.services.crawler.tasks import (
    job_sync_1m, 
    job_sync_1h, 
    job_sync_1d, 
    job_sync_news,
    job_monitor_positions
)

router = APIRouter()

@router.post("/sync/1m")
async def trigger_sync_1m(background_tasks: BackgroundTasks):
    """Trigger 1-minute candle sync for active symbols"""
    background_tasks.add_task(job_sync_1m)
    return {"status": "triggered", "task": "sync_1m"}

@router.post("/sync/1h")
async def trigger_sync_1h(background_tasks: BackgroundTasks):
    """Trigger 1-hour candle sync for active symbols"""
    background_tasks.add_task(job_sync_1h)
    return {"status": "triggered", "task": "sync_1h"}

@router.post("/sync/1d")
async def trigger_sync_1d(background_tasks: BackgroundTasks):
    """Trigger daily candle sync for active symbols"""
    background_tasks.add_task(job_sync_1d)
    return {"status": "triggered", "task": "sync_1d"}

@router.post("/sync/news")
async def trigger_sync_news(background_tasks: BackgroundTasks):
    """Trigger news sync"""
    background_tasks.add_task(job_sync_news)
    return {"status": "triggered", "task": "sync_news"}

@router.post("/monitor")
async def trigger_monitor(background_tasks: BackgroundTasks):
    """Trigger position monitoring (Guardian)"""
    background_tasks.add_task(job_monitor_positions)
    return {"status": "triggered", "task": "monitor_positions"}
