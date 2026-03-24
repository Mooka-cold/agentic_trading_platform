from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import math
import json
import hashlib
import redis.asyncio as redis
from app.db.session import get_user_db
from app.services.execution.service import ExecutionService
from app.api.v1.deps import get_runtime_user_id
from app.core.config import settings

class TradeAction(BaseModel):
    action: str  # BUY/SELL
    symbol: str
    quantity: float
    price: float  # Current market price for execution
    confidence: float
    order_type: Optional[str] = "MARKET"
    trigger_condition: Optional[str] = None
    idempotency_key: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    session_id: Optional[str] = None

class RiskConfigUpdate(BaseModel):
    daily_loss_limit_pct: Optional[float] = None
    max_drawdown_limit_pct: Optional[float] = None

class CancelPendingRequest(BaseModel):
    symbol: Optional[str] = None

router = APIRouter()

@router.post("/execute")
async def execute_trade(
    trade: TradeAction,
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    """
    Execute a trade via Execution Service (Supports PAPER and LIVE modes).
    """
    service = ExecutionService(db, user_id=user_id)
    redis_client = None
    lock_key = None
    response_key = None
    
    try:
        raw_idempotency_key = (trade.idempotency_key or "").strip()
        if raw_idempotency_key:
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            idem_hash = hashlib.sha256(f"{user_id}:{raw_idempotency_key}".encode("utf-8")).hexdigest()
            lock_key = f"idem:trade:{idem_hash}:lock"
            response_key = f"idem:trade:{idem_hash}:resp"

            cached_payload = await redis_client.get(response_key)
            if cached_payload:
                replay = json.loads(cached_payload)
                if isinstance(replay, dict):
                    replay["idempotent_replay"] = True
                    return replay

            locked = await redis_client.set(lock_key, "1", ex=120, nx=True)
            if not locked:
                raise HTTPException(status_code=409, detail="Duplicate request in progress")

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
        order_type_val = getattr(trade, 'order_type', None)
        order_type = order_type_val.upper() if order_type_val else "MARKET"
        
        # If trigger_condition has a price, use it for limit/stop orders
        # Example trigger_condition format: "price <= 70000" or just a number string "70000"
        trigger_price = None
        trigger_condition = getattr(trade, 'trigger_condition', None)
        if trigger_condition and order_type != 'MARKET':
            import re
            matches = re.findall(r"[-+]?\d*\.\d+|\d+", trigger_condition)
            if matches:
                trigger_price = float(matches[-1])

        _, execution_info = service.place_order(
            symbol=trade.symbol,
            side=side,
            order_type=order_type,
            quantity=trade.quantity,
            current_price=trade.price,
            trigger_price=trigger_price,
            sl=trade.stop_loss,
            tp=trade.take_profit,
            session_id=trade.session_id,
            user_id=user_id
        )
        
        # Fetch updated balance
        new_balance = service.get_balance()
        
        exec_status = execution_info.get("status")
        if exec_status == "PENDING":
            response_status = "ACCEPTED"
            response_message = "Order placed in Pending pool"
        elif exec_status:
            response_status = exec_status
            response_message = "Order executed" if exec_status == "FILLED" else f"Order {exec_status.lower()}"
        else:
            response_status = "FILLED"
            response_message = "Order executed"

        response_payload = {
            "status": response_status,
            "message": response_message,
            "order_id": execution_info.get("order_id"),
            "executed_price": trade.price if execution_info.get("status") != "PENDING" else trigger_price,
            "mode": execution_info.get("mode", "UNKNOWN"),
            "pnl": execution_info.get("pnl", 0.0),
            "new_balance": new_balance,
            "leverage_guard": execution_info.get("leverage_guard"),
        }
        if redis_client and response_key:
            await redis_client.set(response_key, json.dumps(response_payload, ensure_ascii=False), ex=900)
        return response_payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if redis_client and lock_key:
            try:
                await redis_client.delete(lock_key)
            except Exception:
                pass
        if redis_client:
            try:
                await redis_client.close()
            except Exception:
                pass

@router.get("/positions")
async def get_positions(
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    """
    Get all open positions.
    """
    service = ExecutionService(db, user_id=user_id)
    try:
        return service.get_all_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders")
async def get_order_history(
    limit: int = 20,
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    """
    Get recent order history.
    """
    service = ExecutionService(db, user_id=user_id)
    try:
        # ExecutionService uses PaperTradingService internally for PAPER mode
        # We need to expose get_order_history in ExecutionService or access paper_service directly
        if service.mode == "PAPER":
            # Use adapter method which returns dicts
            return service.adapter.get_order_history(user_id=user_id, limit=limit)
        else:
            # LIVE mode not implemented for history yet
            return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders/pending")
async def get_pending_orders(
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    """
    Get all pending (LIMIT/STOP) orders.
    """
    service = ExecutionService(db, user_id=user_id)
    try:
        if service.mode == "PAPER":
            orders = service.paper_service.get_pending_orders(user_id=user_id)
            return [
                {
                    "id": str(o.id),
                    "symbol": o.symbol,
                    "side": o.side,
                    "type": o.type,
                    "price": float(o.price) if o.price else 0.0,
                    "quantity": float(o.quantity),
                    "status": o.status,
                    "created_at": o.created_at.isoformat() if o.created_at else None
                }
                for o in orders
            ]
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/orders/pending/cancel-all")
async def cancel_all_pending_orders(
    req: CancelPendingRequest,
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    service = ExecutionService(db, user_id=user_id)
    try:
        if service.mode != "PAPER":
            return {"cancelled": 0, "symbol": req.symbol, "mode": service.mode}
        return service.paper_service.cancel_pending_orders(user_id=user_id, symbol=req.symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paper/account")
async def get_paper_account(
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    """
    Get detailed paper account status (Balance, Equity, PnL).
    """
    service = ExecutionService(db, user_id=user_id)
    if service.mode != "PAPER":
        raise HTTPException(status_code=400, detail="Not in PAPER mode")
        
    try:
        # Get raw account from paper service
        account = service.paper_service.get_or_create_account(user_id=user_id)
        # Calculate live equity
        equity = service.paper_service.get_equity(
            user_id=user_id,
            current_prices=service.paper_service._get_latest_prices(
                [p.symbol for p in service.paper_service.get_open_positions(user_id=user_id)]
            ),
        )
        
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
async def check_portfolio_risk(
    current_equity: Optional[float] = None,
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    """
    Check if portfolio is within risk limits (Daily Loss, Max Drawdown).
    """
    service = ExecutionService(db, user_id=user_id)
    try:
        return service.check_portfolio_risk(current_equity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk/reset-daily")
async def reset_daily_risk_metrics(
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    service = ExecutionService(db, user_id=user_id)
    try:
        if service.mode != "PAPER":
            return {"status": "skipped", "reason": "only supported in PAPER mode"}
        return service.paper_service.reset_daily_metrics_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk/state")
async def get_risk_state(
    current_equity: Optional[float] = None,
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    service = ExecutionService(db, user_id=user_id)
    try:
        if service.mode != "PAPER":
            return {"status": "skipped", "reason": "only supported in PAPER mode"}
        return service.paper_service.get_risk_state(user_id=user_id, current_equity=current_equity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk/config")
async def update_risk_config(
    payload: RiskConfigUpdate,
    db: Session = Depends(get_user_db),
    user_id: int = Depends(get_runtime_user_id),
):
    service = ExecutionService(db, user_id=user_id)
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
        return service.paper_service.get_risk_state(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from app.services.paper_trading import SessionReflection

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
from datetime import datetime, timedelta, timezone

@router.get("/reflection/pending")
def get_pending_reviews(db: Session = Depends(get_user_db)):
    """
    Find sessions that need periodic review (T+1h, T+6h, T+24h).
    """
    now = datetime.now(timezone.utc)
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
