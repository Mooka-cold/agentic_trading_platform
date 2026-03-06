from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services.llm_service import LLMService
from services.redis_stream import redis_stream
from services.watcher import WatcherService
from workflow import WorkflowEngine
from core.prompt_loader import registry
from sse_starlette.sse import EventSourceResponse
import asyncio

app = FastAPI(title="AI Engine", version="0.1.0")

# Force reload trigger - 2024-03-02
# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_service = LLMService()
workflow_engine = WorkflowEngine()
watcher_service = WatcherService(workflow_engine)


@app.on_event("startup")
async def startup_event():
    print("Starting AI Engine...")
    await watcher_service.start()
    
    # Check if loop should be running (restore state)
    try:
        import json
        redis_client = workflow_engine.redis_client
        loop_active = await redis_client.get("system_status:loop_active")
        if loop_active and loop_active.decode() == "true":
            config_str = await redis_client.get("system_status:loop_config")
            if config_str:
                config = json.loads(config_str)
                symbol = config.get("symbol", "BTC/USDT")
                session_id = config.get("session_id", "restored-session")
                print(f"Restoring active loop for {symbol}...")
                await workflow_engine.start_loop(symbol, session_id)
    except Exception as e:
        print(f"Failed to restore loop state: {e}")
    

@app.on_event("shutdown")
async def shutdown_event():
    await watcher_service.stop()
    await workflow_engine.close()

class AnalysisRequest(BaseModel):
    symbol: str
    session_id: Optional[str] = None
    market_context: Optional[str] = None
    news_context: Optional[str] = None

class UserConfigUpdate(BaseModel):
    config: Dict[str, Any]

@app.post("/analyze")
async def analyze_market(req: AnalysisRequest):
    # Trigger LLM analysis
    # Currently we ignore passed context and fetch fresh data inside LLMService
    # In future, we can merge both.
    
    result = await llm_service.analyze(req.symbol)
    return result

@app.post("/workflow/run")
async def run_workflow_endpoint(req: AnalysisRequest):
    """
    Start or Update Continuous Workflow Loop
    """
    session_id = req.session_id or "continuous_session"
    # Start loop (or update config if running)
    await workflow_engine.start_loop(req.symbol, session_id)
    return {"status": "started", "session_id": session_id, "mode": "continuous"}

@app.post("/workflow/trigger")
async def trigger_workflow_endpoint(req: AnalysisRequest):
    """
    Force trigger a workflow cycle (e.g. from Watcher).
    Skips if engine is busy.
    """
    import time
    session_id = req.session_id or f"trigger-{int(time.time())}"
    
    # Run in background
    asyncio.create_task(workflow_engine.run_workflow(req.symbol, session_id))
    return {"status": "triggered", "session_id": session_id}

@app.post("/workflow/review/periodic")
async def trigger_periodic_review():
    """
    Trigger Multi-Stage Periodic Review (1H, 6H, 24H, Final).
    Should be called by a Cron job every hour.
    """
    asyncio.create_task(workflow_engine.reflector.run_periodic_reviews())
    return {"status": "periodic_review_triggered"}

@app.get("/workflow/status")
async def workflow_status_endpoint():
    """
    Get current workflow status
    """
    return {
        "is_running": workflow_engine.is_running,
        "symbol": workflow_engine.latest_config.get("symbol"),
        "session_id": workflow_engine.latest_config.get("session_id")
    }

@app.post("/workflow/stop")
async def stop_workflow_endpoint():
    """
    Stop Continuous Workflow Loop
    """
    await workflow_engine.stop_loop()
    return {"status": "stopped"}

@app.get("/stream/logs/{session_id}")
async def stream_logs(session_id: str, request: Request):
    """
    SSE Endpoint for real-time agent logs
    """
    async def event_generator():
        stream = redis_stream.subscribe_channel(f"agent_stream:{session_id}")
        try:
            async for message in stream:
                if await request.is_disconnected():
                    break
                yield {"data": message}
        except Exception as e:
            print(f"Stream error: {e}")

    return EventSourceResponse(event_generator())

@app.get("/stream/monitor/{symbol}")
async def stream_monitor(symbol: str, request: Request):
    """
    SSE Endpoint for real-time monitoring of a symbol (Continuous Mode)
    """
    async def event_generator():
        # Handle slash in symbol if encoded, e.g. BTC%2FUSDT -> BTC/USDT
        # Actually symbol param is already decoded by FastAPI if passed as path param?
        # But slash in path param is tricky. 
        # Better to pass encoded or handle 'BTC-USDT'
        # BaseAgent logic: "auto-BTC/USDT-xxx" -> target_symbol="BTC/USDT"
        # Redis channel: "agent_monitor:BTC/USDT"
        
        # If symbol comes as "BTC-USDT" from frontend (safe URL), replace with slash if needed?
        # Let's assume frontend passes "BTC/USDT" properly encoded.
        # But if path param has slash, it breaks routing.
        # Workaround: Use query param or catch-all path.
        # Or simple: Frontent uses query param ?symbol=...
        # But here it is path param.
        # Let's change to query param to be safe.
        pass # Replaced by logic below

@app.get("/stream/monitor")
async def stream_monitor_query(symbol: str, request: Request):
    """
    SSE Endpoint for real-time monitoring.
    Usage: /stream/monitor?symbol=BTC/USDT
    """
    async def event_generator():
        channel = f"agent_monitor:{symbol}"
        print(f"Monitor subscribing to: {channel}")
        stream = redis_stream.subscribe_channel(channel)
        try:
            async for message in stream:
                if await request.is_disconnected():
                    break
                yield {"data": message}
        except Exception as e:
            print(f"Stream error: {e}")

    return EventSourceResponse(event_generator())

@app.get("/prompts/{agent_name}/config")
async def get_agent_config(agent_name: str, user_variant: str = "default"):
    """
    Get the current user configuration for a specific agent.
    """
    try:
        config = registry.get_user_config(agent_name, user_variant)
        return {"agent": agent_name, "variant": user_variant, "config": config}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/prompts/{agent_name}/config")
async def update_agent_config(agent_name: str, update: UserConfigUpdate, user_variant: str = "default"):
    """
    Update the user configuration for a specific agent.
    """
    try:
        registry.update_user_config(agent_name, update.config, user_variant)
        return {"status": "success", "message": f"Config updated for {agent_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-engine"}
