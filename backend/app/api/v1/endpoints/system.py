from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import httpx
import uuid
from app.core.config import settings
from app.db.session import get_user_db
from shared.models.system import SystemConfig
from shared.models.user import UserPrompt, UserAutomationRule, SystemPersona, UserTeamConfig
from app.schemas.system import SystemConfigCreate, SystemConfig as SystemConfigSchema
from app.api.v1.deps import get_runtime_user_id

router = APIRouter()

@router.post("/reload")
async def reload_ai_engine():
    """Trigger AI Engine to reload configuration"""
    async with httpx.AsyncClient() as client:
        try:
            workflow_url = f"{settings.AI_ENGINE_URL}/workflow/reload"
            sentiment_url = f"{settings.AI_ENGINE_URL}/sentiment/reload-config"
            workflow_resp = await client.post(workflow_url)
            sentiment_resp = await client.post(sentiment_url)
            if workflow_resp.status_code != 200:
                raise HTTPException(status_code=workflow_resp.status_code, detail="AI Engine workflow reload failed")
            if sentiment_resp.status_code != 200:
                raise HTTPException(status_code=sentiment_resp.status_code, detail="AI Engine sentiment reload failed")
            return {
                "workflow": workflow_resp.json(),
                "sentiment": sentiment_resp.json()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reload AI Engine: {e}")



@router.get("/sentiment/interpretations")
async def get_sentiment_interpretations(symbol: str, limit: int = 20, scope: str = "symbol"):
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(
                f"{settings.AI_ENGINE_URL}/sentiment/interpretations",
                params={"symbol": symbol, "limit": limit, "scope": scope},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sentiment interpretations: {e}")



@router.get("/prompts")
def get_user_prompts(user_id: uuid.UUID = Depends(get_runtime_user_id), db: Session = Depends(get_user_db)):
    """获取当前用户的所有自定义 Prompt"""
    prompts = db.query(UserPrompt).filter(UserPrompt.user_id == user_id).all()
    return [{"id": str(p.id), "agent_role": p.agent_role, "system_prompt_override": p.system_prompt_override, "is_active": p.is_active} for p in prompts]

@router.put("/prompts/{agent_role}")
def update_user_prompt(
    agent_role: str,
    payload: Dict[str, Any] = Body(...),
    user_id: uuid.UUID = Depends(get_runtime_user_id),
    db: Session = Depends(get_user_db)
):
    """更新或创建特定角色的自定义 Prompt"""
    prompt = db.query(UserPrompt).filter(UserPrompt.user_id == user_id, UserPrompt.agent_role == agent_role).first()
    
    override = payload.get("system_prompt_override")
    is_active = payload.get("is_active", True)
    
    if prompt:
        prompt.system_prompt_override = override
        prompt.is_active = is_active
    else:
        prompt = UserPrompt(user_id=user_id, agent_role=agent_role, system_prompt_override=override, is_active=is_active)
        db.add(prompt)
        
    db.commit()
    return {"status": "success", "agent_role": agent_role}

@router.get("/automation/rules")
def get_user_automation_rules(user_id: uuid.UUID = Depends(get_runtime_user_id), db: Session = Depends(get_user_db)):
    """获取当前用户的所有自动化规则"""
    rules = db.query(UserAutomationRule).filter(UserAutomationRule.user_id == user_id).all()
    return [{
        "id": str(r.id),
        "symbol": r.symbol,
        "rule_type": r.rule_type,
        "condition_payload": r.condition_payload,
        "action_payload": r.action_payload,
        "is_active": r.is_active
    } for r in rules]

from app.services.llm_gateway import llm_gateway
from app.services.trigger_engine import trigger_engine

@router.post("/llm/invoke")
async def invoke_llm_gateway(payload: Dict[str, Any] = Body(...)):
    """
    LLM 网关代理接口，供 Agent Runtime 调用
    """
    user_id = payload.get("user_id", "default")
    messages = payload.get("messages", [])
    output_schema = payload.get("output_schema")
    
    result = await llm_gateway.invoke(user_id, messages, output_schema)
    return result

@router.post("/trigger/cron")
async def trigger_cron_rules():
    """Evaluate and trigger all active CRON rules"""
    await trigger_engine.evaluate_cron_rules()
    return {"status": "ok"}

@router.post("/trigger/market")
async def trigger_market_rules(payload: Dict[str, Any] = Body(...)):
    """Evaluate and trigger rules based on market data updates"""
    symbol = payload.get("symbol")
    market_context = payload.get("market_context", {})
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    await trigger_engine.process_market_event(symbol, market_context)
    return {"status": "ok"}

@router.get("/session-mgr/context/{user_id}")
def get_user_session_context(
    user_id: uuid.UUID, 
    request: Request,
    db: Session = Depends(get_user_db),
    user_id_dep: uuid.UUID = Depends(get_runtime_user_id)
):
    if request.headers.get("X-Internal-Service") == "ai_engine":
        internal_user_id = request.headers.get("X-User-Id")
        if not internal_user_id or str(user_id) != internal_user_id:
            raise HTTPException(status_code=403, detail="Forbidden: X-User-Id mismatch")
    else:
        if user_id != user_id_dep:
            raise HTTPException(status_code=403, detail="Forbidden: You can only access your own session context")
        
    from app.services.session_mgr import SessionManager
    mgr = SessionManager(db)
    context = mgr.build_decision_context(user_id)
    return context
@router.post("/automation/rules")
def create_automation_rule(
    payload: Dict[str, Any] = Body(...),
    user_id: uuid.UUID = Depends(get_runtime_user_id),
    db: Session = Depends(get_user_db)
):
    """创建自动化规则"""
    rule = UserAutomationRule(
        user_id=user_id,
        symbol=payload.get("symbol", "ALL"),
        rule_type=payload.get("rule_type"),
        condition_payload=payload.get("condition_payload", {}),
        action_payload=payload.get("action_payload", {}),
        is_active=payload.get("is_active", True)
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"status": "success", "id": str(rule.id)}

@router.get("/personas")
def get_system_personas(db: Session = Depends(get_user_db)):
    """获取所有系统预设人格"""
    personas = db.query(SystemPersona).filter(SystemPersona.is_active == True).all()
    # Debug log to see how many personas we're actually returning
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Returning {len(personas)} personas from DB")
    return [{
        "id": p.id,
        "name": p.name,
        "role_type": p.role_type,
        "description": p.description,
        "prompt_template": p.prompt_template
    } for p in personas]

@router.get("/team-config")
def get_user_team_config(user_id: uuid.UUID = Depends(get_runtime_user_id), db: Session = Depends(get_user_db)):
    """获取当前用户的交易天团配置"""
    config = db.query(UserTeamConfig).filter(UserTeamConfig.user_id == user_id).first()
    if not config:
        # Return a default empty structure if none exists
        return {
            "market_agent_ids": [],
            "strategy_agent_ids": [],
            "risk_agent_ids": [],
            "finalizer_agent_id": None
        }
    return {
        "market_agent_ids": config.market_agent_ids,
        "strategy_agent_ids": config.strategy_agent_ids,
        "risk_agent_ids": config.risk_agent_ids,
        "finalizer_agent_id": config.finalizer_agent_id
    }

@router.put("/team-config")
def update_user_team_config(
    payload: Dict[str, Any] = Body(...),
    user_id: uuid.UUID = Depends(get_runtime_user_id),
    db: Session = Depends(get_user_db)
):
    """更新用户的交易天团配置"""
    config = db.query(UserTeamConfig).filter(UserTeamConfig.user_id == user_id).first()

    market_agent_ids = payload.get("market_agent_ids", [])
    strategy_agent_ids = payload.get("strategy_agent_ids", [])
    risk_agent_ids = payload.get("risk_agent_ids", [])
    finalizer_agent_id = payload.get("finalizer_agent_id")

    if config:
        config.market_agent_ids = market_agent_ids
        config.strategy_agent_ids = strategy_agent_ids
        config.risk_agent_ids = risk_agent_ids
        config.finalizer_agent_id = finalizer_agent_id
    else:
        config = UserTeamConfig(
            user_id=user_id,
            market_agent_ids=market_agent_ids,
            strategy_agent_ids=strategy_agent_ids,
            risk_agent_ids=risk_agent_ids,
            finalizer_agent_id=finalizer_agent_id
        )
        db.add(config)
        
    db.commit()
    return {"status": "success"}

@router.get("/config", response_model=List[SystemConfigSchema])
def get_configs(db: Session = Depends(get_user_db)):
    configs = db.query(SystemConfig).all()
    return configs

@router.post("/config", response_model=SystemConfigSchema)
def set_config(config: SystemConfigCreate, db: Session = Depends(get_user_db)):
    db_config = db.query(SystemConfig).filter(SystemConfig.key == config.key).first()
    if db_config:
        db_config.value = config.value
        if config.description is not None:
            db_config.description = config.description
    else:
        db_config = SystemConfig(key=config.key, value=config.value, description=config.description)
        db.add(db_config)
    
    db.commit()
    db.refresh(db_config)
    return db_config

@router.get("/config/{key}", response_model=SystemConfigSchema)
def get_config_by_key(key: str, db: Session = Depends(get_user_db)):
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


# ─── Data Freshness endpoint ────────────────────────────────

@router.get("/data-freshness")
def get_data_freshness(
    symbol: str = "BTC/USDT",
    db_user: Session = Depends(get_user_db),
):
    """
    Aggregate data-freshness for K-line (market DB), News (user DB), and On-chain (user DB).
    Returns a structured snapshot that the frontend Dashboard / Swarm page can render
    as a "data health" banner so users can see *which* feeds are stale at a glance.
    """
    import datetime
    from sqlalchemy import create_engine, text
    from shared.models.news import News

    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    results: Dict[str, Any] = {"symbol": symbol, "ts": now.isoformat(), "sources": {}}

    # K-line freshness by interval
    try:
        market_engine = create_engine(settings.DATABASE_MARKET_URL)
        with market_engine.connect() as conn:
            for interval in ["1m", "5m", "15m", "1h"]:
                row = conn.execute(
                    text("SELECT MAX(time) AS last, COUNT(*) AS n FROM market_klines WHERE symbol=:s AND interval=:i"),
                    {"s": symbol, "i": interval},
                ).fetchone()
                if not row or not row.last:
                    results["sources"][f"klines_{interval}"] = {
                        "status": "missing",
                        "age_seconds": None,
                        "n_rows": 0,
                    }
                    continue
                last_ts = row.last.replace(tzinfo=datetime.timezone.utc)
                age = int((now - last_ts).total_seconds())
                # Define per-interval freshness thresholds (in seconds)
                thresholds = {"1m": 5 * 60, "5m": 15 * 60, "15m": 45 * 60, "1h": 150 * 60}
                threshold = thresholds.get(interval, 5 * 60)
                status = "fresh" if age <= threshold else "stale" if age <= threshold * 4 else "very_stale"
                results["sources"][f"klines_{interval}"] = {
                    "status": status,
                    "last_ts": last_ts.isoformat(),
                    "age_seconds": age,
                    "threshold_seconds": threshold,
                    "n_rows": int(row.n),
                }
    except Exception as e:
        results["sources"]["klines"] = {"status": "error", "error": str(e)}

    # News freshness by source
    try:
        sources = (
            db_user.query(News.source, News.published_at)
            .order_by(News.source, News.published_at.desc())
            .all()
        )
        latest_by_source: Dict[str, Any] = {}
        for src, pub in sources:
            if src not in latest_by_source:
                latest_by_source[src] = pub
        for src, last_pub in latest_by_source.items():
            last_ts = last_pub.replace(tzinfo=datetime.timezone.utc)
            age = int((now - last_ts).total_seconds())
            threshold = 30 * 60  # 30 minutes for news
            status = "fresh" if age <= threshold else "stale" if age <= 6 * 3600 else "very_stale"
            results["sources"][f"news_{src}"] = {
                "status": status,
                "last_ts": last_ts.isoformat(),
                "age_seconds": age,
                "threshold_seconds": threshold,
            }
    except Exception as e:
        results["sources"]["news"] = {"status": "error", "error": str(e)}

    # Overall verdict: any very_stale in klines → degraded; any stale in klines → warn; else healthy
    kline_statuses = [v.get("status") for k, v in results["sources"].items() if k.startswith("klines_")]
    if any(s == "very_stale" for s in kline_statuses):
        overall = "degraded"
    elif any(s == "stale" for s in kline_statuses):
        overall = "warn"
    elif any(s == "missing" for s in kline_statuses):
        overall = "degraded"
    else:
        overall = "healthy"
    results["overall"] = overall

    return results
