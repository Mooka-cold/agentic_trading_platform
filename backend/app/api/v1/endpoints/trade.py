from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import math
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

class RiskConfigUpdate(BaseModel):
    daily_loss_limit_pct: Optional[float] = None
    max_drawdown_limit_pct: Optional[float] = None

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
            "CLOSE_SHORT": "BUY",
            "FLIP_TO_LONG": "BUY",
            "FLIP_TO_SHORT": "SELL"
        }
        raw_action = trade.action.upper()
        
        if raw_action not in action_map:
            # Fallback or Error
            raise HTTPException(status_code=400, detail=f"Invalid action: {raw_action}. Use BUY/SELL/LONG/SHORT/COVER/FLIP.")
            
        side = action_map[raw_action]

        result = service.execute_order(
            symbol=trade.symbol,
            side=side,
            quantity=trade.quantity,
            price=trade.price,
            params={
                "stop_loss": trade.stop_loss, 
                "take_profit": trade.take_profit,
                "session_id": trade.session_id,
                "intent": raw_action # Pass original intent if possible? No, execute_order logic infers it.
                # Actually, we should let execute_order infer the intent based on position state.
                # But if the user explicitly says "FLIP", we should probably respect it?
                # The current logic in PaperTradingService infers intent automatically.
                # So we just pass the side.
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
            "closed_session_id": result.get("closed_session_id"),
            "intent": result.get("intent")
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

@router.get("/orders")
async def get_order_history(limit: int = 20, db: Session = Depends(get_user_db)):
    """
    Get recent order history.
    """
    service = ExecutionService(db, user_id=1)
    try:
        # ExecutionService uses PaperTradingService internally for PAPER mode
        # We need to expose get_order_history in ExecutionService or access paper_service directly
        if service.mode == "PAPER":
            # Use adapter method which returns dicts
            return service.adapter.get_order_history(user_id=1, limit=limit)
        else:
            # LIVE mode not implemented for history yet
            return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paper/account")
async def get_paper_account(db: Session = Depends(get_user_db)):
    """
    Get detailed paper account status (Balance, Equity, PnL).
    """
    service = ExecutionService(db, user_id=1)
    if service.mode != "PAPER":
        raise HTTPException(status_code=400, detail="Not in PAPER mode")
        
    try:
        # Get raw account from paper service
        account = service.paper_service.get_or_create_account(user_id=1)
        # Calculate live equity
        equity = service.paper_service.get_equity(user_id=1, current_prices=service.paper_service._get_latest_prices([p.symbol for p in service.paper_service.get_open_positions(user_id=1)]))
        
        return {
            "balance": float(account.balance),
            "equity": equity,
            "currency": account.currency,
            "unrealized_pnl": equity - float(account.balance),
            "daily_start": float(account.daily_start_balance),
            "is_locked": account.is_locked,
            "lock_reason": account.lock_reason
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk/check")
async def check_portfolio_risk(current_equity: Optional[float] = None, db: Session = Depends(get_user_db)):
    """
    Check if portfolio is within risk limits (Daily Loss, Max Drawdown).
    """
    service = ExecutionService(db, user_id=1)
    try:
        return service.check_portfolio_risk(current_equity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk/reset-daily")
async def reset_daily_risk_metrics(db: Session = Depends(get_user_db)):
    service = ExecutionService(db, user_id=1)
    try:
        if service.mode != "PAPER":
            return {"status": "skipped", "reason": "only supported in PAPER mode"}
        return service.paper_service.reset_daily_metrics_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk/state")
async def get_risk_state(current_equity: Optional[float] = None, db: Session = Depends(get_user_db)):
    service = ExecutionService(db, user_id=1)
    try:
        if service.mode != "PAPER":
            return {"status": "skipped", "reason": "only supported in PAPER mode"}
        return service.paper_service.get_risk_state(user_id=1, current_equity=current_equity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk/config")
async def update_risk_config(payload: RiskConfigUpdate, db: Session = Depends(get_user_db)):
    service = ExecutionService(db, user_id=1)
    try:
        if service.mode != "PAPER":
            return {"status": "skipped", "reason": "only supported in PAPER mode"}
        updates = {}
        if payload.daily_loss_limit_pct is not None:
            raw = float(payload.daily_loss_limit_pct)
            if not math.isfinite(raw):
                raise HTTPException(status_code=400, detail="Invalid daily_loss_limit_pct")
            val = min(max(raw, 0.001), 0.99)
            updates["PAPER_DAILY_LOSS_LIMIT_PCT"] = val
        if payload.max_drawdown_limit_pct is not None:
            raw = float(payload.max_drawdown_limit_pct)
            if not math.isfinite(raw):
                raise HTTPException(status_code=400, detail="Invalid max_drawdown_limit_pct")
            val = min(max(raw, 0.001), 0.99)
            updates["PAPER_MAX_DRAWDOWN_LIMIT_PCT"] = val
        from shared.models.system import SystemConfig
        for key, value in updates.items():
            cfg = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if cfg:
                cfg.value = str(value)
            else:
                db.add(SystemConfig(key=key, value=str(value), description="paper risk config"))
        db.commit()
        return service.paper_service.get_risk_state(user_id=1)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from shared.models.market import MarketKline
from app.services.paper_trading import PaperPosition

from app.services.paper_trading import PaperOrder, SessionReflection

@router.post("/reflection")
async def save_reflection(
    data: dict, 
    db: Session = Depends(get_user_db)
):
    """
    Save structured reflection from AI Agent.
    """
    try:
        # data expected:
        # {
        #   "session_id": "...",
        #   "stage": "IMMEDIATE" | "T_PLUS_1H" ...,
        #   "content": "JSON string",
        #   "score": 8.5,
        #   "market_context": "..."
        # }
        
        reflection = SessionReflection(
            session_id=data['session_id'],
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

from shared.models.workflow import WorkflowSession, WorkflowStatus
from datetime import datetime, timedelta

@router.get("/reflection/pending")
def get_pending_reviews(db: Session = Depends(get_user_db)):
    """
    Find sessions that need periodic review (T+1h, T+6h, T+24h).
    """
    now = datetime.utcnow()
    tasks = []
    
    # 1. Check T+1H (Sessions finished > 1h ago, status=PENDING)
    # Logic: If current time is 10:00, and session ended at 08:50 (1h 10m ago), it needs review.
    # Condition: end_time <= now - 1h
    t1_threshold = now - timedelta(hours=1)
    
    sessions_t1 = db.query(WorkflowSession).filter(
        WorkflowSession.end_time <= t1_threshold,
        WorkflowSession.periodic_review_status == "PENDING",
        WorkflowSession.status == WorkflowStatus.COMPLETED
    ).all()
    
    for s in sessions_t1:
        tasks.append({
            "session_id": s.id, 
            "stage": "T_PLUS_1H", 
            "symbol": s.symbol, 
            "action": s.action
        })
    
    # Debug log for T+1H check
    print(f"DEBUG: T+1H Check at {now}, Threshold: {t1_threshold}, Found: {len(sessions_t1)}")
    if len(sessions_t1) > 0:
        for s in sessions_t1:
            print(f"DEBUG: Found T1 Candidate: {s.id}, EndTime: {s.end_time}")

    # 2. Check T+6H (finished > 6h ago, status=T1_DONE)
    t6_threshold = now - timedelta(hours=6)
    sessions_t6 = db.query(WorkflowSession).filter(
        WorkflowSession.end_time <= t6_threshold,
        WorkflowSession.periodic_review_status == "T1_DONE"
    ).all()
    for s in sessions_t6:
        tasks.append({
            "session_id": s.id, 
            "stage": "T_PLUS_6H", 
            "symbol": s.symbol, 
            "action": s.action
        })

    # 3. Check T+24H (finished > 24h ago, status=T6_DONE)
    t24_threshold = now - timedelta(hours=24)
    sessions_t24 = db.query(WorkflowSession).filter(
        WorkflowSession.end_time <= t24_threshold,
        WorkflowSession.periodic_review_status == "T6_DONE"
    ).all()
    for s in sessions_t24:
        tasks.append({
            "session_id": s.id, 
            "stage": "T_PLUS_24H", 
            "symbol": s.symbol, 
            "action": s.action
        })

    return tasks
