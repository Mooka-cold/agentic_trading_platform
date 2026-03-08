from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.db.session import get_user_db
from app.services.execution.service import ExecutionService

class TradeAction(BaseModel):
    action: str  # BUY/SELL
    symbol: str
    quantity: float
    price: float  # Current market price for execution
    confidence: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    session_id: Optional[str] = None

router = APIRouter()

@router.post("/execute")
async def execute_trade(trade: TradeAction, db: Session = Depends(get_user_db)):
    """
    Execute a trade via Execution Service (Supports PAPER and LIVE modes).
    """
    # Assuming user_id=1 for MVP
    service = ExecutionService(db, user_id=1)
    
    try:
        # Normalize Action
        action_map = {
            "LONG": "BUY",
            "SHORT": "SELL",
            "BUY": "BUY",
            "SELL": "SELL",
            "COVER": "BUY", # Buy to Cover Short
            "CLOSE": "SELL", # Default to Sell for Close (Assuming Long) - TODO: Check position side
            "CLOSE_LONG": "SELL",
            "CLOSE_SHORT": "BUY"
        }
        raw_action = trade.action.upper()
        
        if raw_action not in action_map:
            # Fallback or Error
            raise HTTPException(status_code=400, detail=f"Invalid action: {raw_action}. Use BUY/SELL/LONG/SHORT/COVER.")
            
        side = action_map[raw_action]

        result = service.execute_order(
            symbol=trade.symbol,
            side=side,
            quantity=trade.quantity,
            price=trade.price,
            params={
                "stop_loss": trade.stop_loss, 
                "take_profit": trade.take_profit,
                "session_id": trade.session_id
            }
        )
        
        # Fetch updated balance
        new_balance = service.get_balance()
        
        return {
            "status": result["status"],
            "order_id": result["order_id"],
            "executed_price": result["executed_price"],
            "new_balance": new_balance,
            "mode": result.get("mode", "UNKNOWN"),
            "pnl": result.get("pnl", 0.0),
            "closed_session_id": result.get("closed_session_id")
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions")
async def get_positions(db: Session = Depends(get_user_db)):
    """
    Get all open positions.
    """
    service = ExecutionService(db, user_id=1)
    try:
        return service.get_all_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/balance")
async def get_balance(currency: str = "USDT", db: Session = Depends(get_user_db)):
    """
    Get current account balance via Execution Service.
    """
    # Assuming user_id=1 for MVP
    service = ExecutionService(db, user_id=1)
    try:
        balance = service.get_balance(currency)
        return {"currency": currency, "balance": balance, "mode": service.mode}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from app.models.market import MarketKline
from app.services.paper_trading import PaperPosition

from app.services.paper_trading import PaperOrder, TradeReflection

@router.post("/reflection")
async def save_reflection(
    data: dict, 
    db: Session = Depends(get_user_db)
):
    """
    Save structured reflection from AI Agent.
    """
    try:
        reflection = TradeReflection(
            session_id=data.get('session_id'),
            # Backward compatibility for 'order_id' if session_id is missing, 
            # though model expects session_id. 
            # If data['order_id'] is present but session_id is not, 
            # we might need to look up session_id from order_id or just store it if model allows.
            # Assuming model has session_id column.
            # Let's check model definition in next step if needed, but standard fix is:
            # session_id=data['session_id'],
            # For now, let's assume agent sends 'session_id'.
            # If agent sends 'order_id', we map it to session_id? No, order_id is for order.
            # We should use session_id for reflection now.
            stage=data['stage'],
            content=data['content'],
            score=data.get('score'),
            market_context=data.get('market_context'),
            price_change_pct=data.get('price_change_pct')
        )
        db.add(reflection)
        db.commit()
        return {"status": "saved", "id": str(reflection.id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reflection/pending")
def get_pending_reflections(db: Session = Depends(get_user_db)):
    """
    Get Workflow Sessions that need periodic review (T+1H, T+6H, etc.)
    Based on session end_time and periodic_review_status.
    """
    now = datetime.now(timezone.utc)
    pending_tasks = []
    
    # Define Review Windows (Hours)
    # T+1H: 1h <= elapsed < 6h, status != T1_DONE
    # T+6H: 6h <= elapsed < 24h, status != T6_DONE
    # T+24H: elapsed >= 24h, status != COMPLETED
    
    # Fetch completed sessions that are not fully reviewed
    # Optimize query: filter by status != COMPLETED
    sessions = db.query(WorkflowSession).filter(
        WorkflowSession.status == WorkflowStatus.COMPLETED,
        WorkflowSession.periodic_review_status != "COMPLETED",
        WorkflowSession.end_time.isnot(None)
    ).all()
    
    for session in sessions:
        if not session.end_time: continue
        
        # Ensure timezone awareness
        end_time = session.end_time
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
            
        elapsed_hours = (now - end_time).total_seconds() / 3600
        
        task = None
        current_status = session.periodic_review_status or "PENDING"
        
        if 1 <= elapsed_hours < 6:
            if current_status == "PENDING":
                task = "T_PLUS_1H"
        elif 6 <= elapsed_hours < 24:
            if current_status in ["PENDING", "T1_DONE"]:
                 task = "T_PLUS_6H"
        elif elapsed_hours >= 24:
             if current_status != "COMPLETED":
                 task = "T_PLUS_24H"
                 
        if task:
            pending_tasks.append({
                "session_id": session.id,
                "symbol": session.symbol,
                "stage": task,
                "action": session.action,
                "review_result": session.review_status,
                "end_time": end_time.isoformat()
            })
            
    return pending_tasks
