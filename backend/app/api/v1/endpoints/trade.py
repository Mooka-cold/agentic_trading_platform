from fastapi import APIRouter
from pydantic import BaseModel

class TradeAction(BaseModel):
    action: str  # BUY/SELL/HOLD
    symbol: str
    amount: float
    confidence: float

router = APIRouter()

@router.post("/execute")
async def execute_trade(trade: TradeAction):
    # TODO: Forward to Freqtrade or AI Executor
    return {"status": "received", "trade_id": "mock_id_123"}
