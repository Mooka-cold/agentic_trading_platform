from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services.llm_service import LLMService
from services.redis_stream import redis_stream
from services.watcher import WatcherService
from services.system_config import system_config_service
from workflow import WorkflowEngine
from core.prompt_loader import registry
from model.policies import OrchestrationConfig, DataRoutingPolicy
from sse_starlette.sse import EventSourceResponse
import asyncio
import time
from contextlib import asynccontextmanager
from shared.core.symbols import get_default_symbol

llm_service = LLMService()
workflow_engine = WorkflowEngine()
watcher_service = WatcherService(workflow_engine)
DEFAULT_SYMBOL = get_default_symbol()


async def _restore_loop_state():
    import json
    redis_client = workflow_engine.redis_client
    loop_active = await redis_client.get("system_status:loop_active")
    if isinstance(loop_active, bytes):
        loop_active = loop_active.decode()
    if loop_active == "true":
        config_str = await redis_client.get("system_status:loop_config")
        if isinstance(config_str, bytes):
            config_str = config_str.decode()
        if config_str:
            config = json.loads(config_str)
            symbol = config.get("symbol", DEFAULT_SYMBOL)
            session_id = config.get("session_id") or f"restored-{int(time.time())}"
            print(f"Restoring active loop for {symbol}...")
            await workflow_engine.start_loop(symbol, session_id)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    print("Starting AI Engine...")
    await watcher_service.start()
    try:
        await _restore_loop_state()
    except Exception as e:
        print(f"Failed to restore loop state: {e}")
    yield
    await watcher_service.stop()
    await workflow_engine.close()

app = FastAPI(title="AI Engine", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    symbol: str
    session_id: Optional[str] = None
    market_context: Optional[str] = None
    news_context: Optional[str] = None

class UserConfigUpdate(BaseModel):
    config: Dict[str, Any]

class SentimentInterpreterRequest(BaseModel):
    symbol: str = DEFAULT_SYMBOL
    claim_limit: int = 200
    concurrency: int = 20

@app.post("/analyze")
async def analyze_market(req: AnalysisRequest):
    # Trigger LLM analysis
    # Currently we ignore passed context and fetch fresh data inside LLMService
    # In future, we can merge both.
    
    result = await llm_service.analyze(req.symbol)
    return result

@app.post("/workflow/review")
async def trigger_periodic_reviews(background_tasks: BackgroundTasks):
    """Trigger periodic review process (T+1/6/24h)"""
    # Run in background to avoid blocking
    # Corrected: Call async function directly in background task? 
    # BackgroundTasks expects a synchronous callable or an async coroutine function (not a coroutine object)
    # But workflow_engine.reflector.run_periodic_reviews is an async method.
    # FastAPI handles async methods in background tasks correctly.
    # However, workflow_engine.reflector might be None if not initialized?
    # It is initialized in __init__ -> reload_agents.
    
    if not workflow_engine.reflector:
        raise HTTPException(status_code=503, detail="Reflector Agent not ready")

    background_tasks.add_task(workflow_engine.reflector.run_periodic_reviews)
    return {"status": "review_triggered"}

@app.post("/workflow/reload")
async def reload_config():
    """Reload agents with latest configuration from DB"""
    try:
        workflow_engine.reload_agents()
        return {"status": "reloaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sentiment/interpreter/run")
async def run_sentiment_interpreter(background_tasks: BackgroundTasks, req: Optional[SentimentInterpreterRequest] = None):
    symbol = req.symbol if req else DEFAULT_SYMBOL
    claim_limit = req.claim_limit if req else 200
    concurrency = req.concurrency if req else 20
    async def _run():
        try:
            await workflow_engine.sentiment_agent.run_news_interpreter_cycle(
                symbol=symbol,
                claim_limit=claim_limit,
                concurrency=concurrency
            )
        except Exception as exc:
            print(f"Sentiment interpreter run failed: {exc}")
    background_tasks.add_task(_run)
    return {"status": "triggered"}

@app.get("/sentiment/aggregate")
async def get_sentiment_aggregate(symbol: str = DEFAULT_SYMBOL):
    from services.sentiment import sentiment_service
    fng = await sentiment_service.get_fear_greed_index() or {"value": 50}
    return sentiment_service.aggregate_interpreted_news(symbol, fng)

@app.get("/sentiment/interpretations")
async def get_sentiment_interpretations(symbol: str = DEFAULT_SYMBOL, limit: int = 20, scope: str = "symbol"):
    from services.sentiment import sentiment_service
    safe_limit = max(1, min(limit, 100))
    safe_scope = "all" if str(scope).lower() == "all" else "symbol"
    return sentiment_service.get_recent_interpretations(target_symbol=symbol, limit=safe_limit, scope=safe_scope)

@app.get("/sentiment/dashboard")
async def get_sentiment_dashboard(symbol: str = DEFAULT_SYMBOL):
    from services.sentiment import sentiment_service
    return sentiment_service.get_sentiment_dashboard(target_symbol=symbol)

@app.get("/sentiment/monitor")
async def get_sentiment_monitor(hours: int = 24):
    from services.sentiment import sentiment_service
    return sentiment_service.get_interpretation_monitor(hours=hours)

@app.post("/sentiment/reload-config")
async def reload_sentiment_config():
    from services.sentiment import sentiment_service
    try:
        active = sentiment_service.reload_tuning_from_system_config()
        return {"status": "reloaded", "active_params": active}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sentiment/active-config")
async def get_sentiment_active_config():
    from services.sentiment import sentiment_service
    return {"active_params": sentiment_service.get_active_tuning_params()}

@app.post("/workflow/run")
async def run_workflow_endpoint(req: AnalysisRequest):
    """
    Start or Update Continuous Workflow Loop
    """
    session_id = req.session_id or workflow_engine.latest_config.get("session_id") or f"continuous-{int(time.time())}"
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


@app.get("/workflow/policies/active")
async def workflow_policies_active():
    orchestration_raw = system_config_service.get_json("WORKFLOW_ORCHESTRATION_CONFIG") or {}
    routing_raw = system_config_service.get_json("DATA_ROUTING_POLICY") or {}
    orchestration = OrchestrationConfig(**orchestration_raw).model_dump()
    routing_policy = DataRoutingPolicy(**routing_raw).model_dump()
    return {
        "orchestration": orchestration,
        "routing_policy": routing_policy,
        "available_analysis_nodes": OrchestrationConfig().enabled_analysis_nodes,
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
        channel = f"agent_monitor:{symbol}"
        print(f"Monitor(path) subscribing to: {channel}")
        stream = redis_stream.subscribe_channel(channel)
        try:
            async for message in stream:
                if await request.is_disconnected():
                    break
                yield {"data": message}
        except Exception as e:
            print(f"Stream error: {e}")

    return EventSourceResponse(event_generator())

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
        default_prompt = registry.get_system_prompt_template(agent_name)
        return {"agent": agent_name, "variant": user_variant, "config": config, "default_prompt": default_prompt}
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
