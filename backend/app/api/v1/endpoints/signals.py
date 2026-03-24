from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_user_db
from shared.models.signal import Signal
from shared.models.system import SystemConfig
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

router = APIRouter()

class SignalSchema(BaseModel):
    id: UUID
    symbol: str
    action: str
    confidence: float
    reasoning: str
    model_used: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[SignalSchema])
def get_signals(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_user_db)
) -> Any:
    """
    Get latest AI signals.
    """
    query = db.query(Signal)
    if symbol:
        query = query.filter(Signal.symbol == symbol)
    
    signals = query.order_by(Signal.created_at.desc()).limit(limit).all()
    return signals

@router.get("/latest", response_model=Optional[SignalSchema])
def get_latest_signal(
    symbol: str = Query(..., description="Symbol to check"),
    db: Session = Depends(get_user_db)
) -> Any:
    """
    Get the absolute latest signal for a symbol.
    """
    signal = db.query(Signal).filter(Signal.symbol == symbol).order_by(Signal.created_at.desc()).first()
    return signal

class ScheduleConfig(BaseModel):
    enabled: bool
    interval: str

@router.get("/schedule", response_model=ScheduleConfig)
def get_schedule_config(db: Session = Depends(get_user_db)) -> Any:
    enabled_cfg = db.query(SystemConfig).filter(SystemConfig.key == "AUTO_TRADING_SCHEDULE_ENABLED").first()
    interval_cfg = db.query(SystemConfig).filter(SystemConfig.key == "AUTO_TRADING_SCHEDULE_INTERVAL").first()
    enabled = str(enabled_cfg.value).strip().lower() == "true" if enabled_cfg else False
    interval = interval_cfg.value if interval_cfg and interval_cfg.value else "1h"
    return ScheduleConfig(enabled=enabled, interval=interval)

@router.post("/schedule")
async def update_schedule(config: ScheduleConfig, db: Session = Depends(get_user_db)) -> Any:
    valid_intervals = {"5m", "15m", "30m", "1h", "4h", "1d"}
    if config.interval not in valid_intervals:
        config.interval = "1h"

    enabled_cfg = db.query(SystemConfig).filter(SystemConfig.key == "AUTO_TRADING_SCHEDULE_ENABLED").first()
    interval_cfg = db.query(SystemConfig).filter(SystemConfig.key == "AUTO_TRADING_SCHEDULE_INTERVAL").first()

    if enabled_cfg:
        enabled_cfg.value = "true" if config.enabled else "false"
    else:
        db.add(SystemConfig(
            key="AUTO_TRADING_SCHEDULE_ENABLED",
            value="true" if config.enabled else "false",
            description="Auto trading scheduler switch"
        ))

    if interval_cfg:
        interval_cfg.value = config.interval
    else:
        db.add(SystemConfig(
            key="AUTO_TRADING_SCHEDULE_INTERVAL",
            value=config.interval,
            description="Auto trading scheduler interval"
        ))

    db.commit()
    return {"status": "success", "message": "Schedule updated", "config": config}
