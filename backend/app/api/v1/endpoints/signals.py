from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_user_db
from app.models.signal import Signal
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

@router.post("/schedule")
async def update_schedule(config: ScheduleConfig):
    """
    Update Auto-Trading Schedule (Mock implementation for MVP)
    """
    # TODO: Implement APScheduler integration
    print(f"[System] Schedule Updated: {config}")
    return {"status": "success", "message": "Schedule updated", "config": config}
