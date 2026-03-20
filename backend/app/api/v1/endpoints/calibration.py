from typing import Any, Dict, Optional
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_user_db
from shared.models.system import SystemConfig
from app.services.llm_calibration import llm_calibration_service


router = APIRouter()

class CalibrationRunRequest(BaseModel):
    symbol: str = "ETH/USDT"
    window_days: int = 14
    tuning_params: Optional[Dict[str, Any]] = None

class CalibrationApplyRequest(BaseModel):
    tuning_params: Dict[str, Any]
    description: Optional[str] = "Applied from calibration UI"

class CalibrationRollbackRequest(BaseModel):
    symbol: str = "ETH/USDT"
    description: Optional[str] = "Rollback to latest calibration report params"


@router.post("/run")
def run_calibration(payload: Optional[CalibrationRunRequest] = None, symbol: str = Query(default="ETH/USDT"), window_days: int = Query(default=14, ge=3, le=90)):
    try:
        final_symbol = payload.symbol if payload else symbol
        final_window_days = payload.window_days if payload else window_days
        if final_window_days < 3 or final_window_days > 90:
            raise HTTPException(status_code=400, detail="window_days must be in [3,90]")
        tuning_params = payload.tuning_params if payload else None
        return llm_calibration_service.run_daily_calibration(symbol=final_symbol, window_days=final_window_days, tuning_params=tuning_params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/latest")
def latest_calibration(symbol: str = Query(default="ETH/USDT")):
    data = llm_calibration_service.get_latest_report(symbol=symbol)
    if not data:
        raise HTTPException(status_code=404, detail="Calibration report not found")
    return data


@router.get("/history")
def calibration_history(symbol: str = Query(default="ETH/USDT"), limit: int = Query(default=30, ge=1, le=180)):
    return {"items": llm_calibration_service.get_history(symbol=symbol, limit=limit)}

@router.get("/candidates")
def calibration_candidates():
    base = llm_calibration_service._default_tuning_params()
    return {"baseline": base, "candidates": llm_calibration_service.build_daily_candidate_params(base)}

@router.post("/apply")
async def apply_calibration_params(payload: CalibrationApplyRequest, db: Session = Depends(get_user_db)):
    normalized = llm_calibration_service._normalize_tuning_params(payload.tuning_params)
    key = "SENTIMENT_TUNING_PARAMS"
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    value = json.dumps(normalized, ensure_ascii=False)
    if config:
        config.value = value
        if payload.description:
            config.description = payload.description
    else:
        config = SystemConfig(key=key, value=value, description=payload.description)
        db.add(config)
    db.commit()
    db.refresh(config)

    sentiment_reload_result: Dict[str, Any] = {"status": "skipped"}
    workflow_reload_result: Dict[str, Any] = {"status": "skipped"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(f"{settings.AI_ENGINE_URL}/sentiment/reload-config")
            sentiment_reload_result = resp.json() if resp.status_code == 200 else {"status": "error", "detail": resp.text}
        except Exception as exc:
            sentiment_reload_result = {"status": "error", "detail": str(exc)}
        try:
            resp = await client.post(f"{settings.AI_ENGINE_URL}/workflow/reload")
            workflow_reload_result = resp.json() if resp.status_code == 200 else {"status": "error", "detail": resp.text}
        except Exception as exc:
            workflow_reload_result = {"status": "error", "detail": str(exc)}
    return {
        "status": "applied",
        "config_key": key,
        "applied_params": normalized,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        "reload": {
            "sentiment": sentiment_reload_result,
            "workflow": workflow_reload_result
        }
    }

@router.post("/rollback")
async def rollback_calibration_params(payload: CalibrationRollbackRequest, db: Session = Depends(get_user_db)):
    latest = llm_calibration_service.get_latest_report(symbol=payload.symbol)
    if not latest:
        raise HTTPException(status_code=404, detail="No calibration report found for rollback")
    params = ((latest.get("metrics") or {}).get("parameters") or None)
    if not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="Latest report has no parameters snapshot")
    normalized = llm_calibration_service._normalize_tuning_params(params)
    key = "SENTIMENT_TUNING_PARAMS"
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    value = json.dumps(normalized, ensure_ascii=False)
    if config:
        config.value = value
        config.description = payload.description
    else:
        config = SystemConfig(key=key, value=value, description=payload.description)
        db.add(config)
    db.commit()
    db.refresh(config)

    sentiment_reload_result: Dict[str, Any] = {"status": "skipped"}
    workflow_reload_result: Dict[str, Any] = {"status": "skipped"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(f"{settings.AI_ENGINE_URL}/sentiment/reload-config")
            sentiment_reload_result = resp.json() if resp.status_code == 200 else {"status": "error", "detail": resp.text}
        except Exception as exc:
            sentiment_reload_result = {"status": "error", "detail": str(exc)}
        try:
            resp = await client.post(f"{settings.AI_ENGINE_URL}/workflow/reload")
            workflow_reload_result = resp.json() if resp.status_code == 200 else {"status": "error", "detail": resp.text}
        except Exception as exc:
            workflow_reload_result = {"status": "error", "detail": str(exc)}
    return {
        "status": "rolled_back",
        "symbol": payload.symbol,
        "config_key": key,
        "applied_params": normalized,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        "reload": {
            "sentiment": sentiment_reload_result,
            "workflow": workflow_reload_result
        }
    }

@router.get("/active")
def get_active_calibration_params(db: Session = Depends(get_user_db)):
    key = "SENTIMENT_TUNING_PARAMS"
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        return {"config_key": key, "applied_params": llm_calibration_service._default_tuning_params(), "source": "default"}
    try:
        parsed = json.loads(config.value or "{}")
    except Exception:
        parsed = llm_calibration_service._default_tuning_params()
    return {
        "config_key": key,
        "applied_params": llm_calibration_service._normalize_tuning_params(parsed),
        "source": "system_configs",
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        "description": config.description
    }
