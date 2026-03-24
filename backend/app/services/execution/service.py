from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.execution.interfaces import ExecutionAdapter
from app.services.execution.paper_adapter import PaperTradingAdapter

class ExecutionService:
    """
    Router for Execution Strategies (Paper vs Live)
    """
    def __init__(self, db: Session, user_id: int = None, mode: str = None):
        self.mode = mode or settings.TRADING_MODE
        self.db = db
        self.user_id = user_id
        
        # Initialize Adapter based on Mode
        if self.mode == "PAPER":
            self.adapter = PaperTradingAdapter(db, user_id)
            # Expose paper_service for direct access if needed (e.g. for history)
            self.paper_service = self.adapter.service 
        elif self.mode == "LIVE":
            if not settings.LIVE_TRADING_ENABLED:
                raise NotImplementedError("Live trading is disabled (LIVE_TRADING_ENABLED=false)")
            # self.adapter = LiveTradingAdapter(db, user_id)
            raise NotImplementedError("Live Trading not yet implemented")
        else:
            raise ValueError(f"Unknown TRADING_MODE: {self.mode}")

    def execute_order(self, symbol: str, side: str, quantity: float, price: float = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Route order to appropriate adapter
        """
        print(f"[ExecutionService] Routing {side} {quantity} {symbol} to {self.mode} Adapter")
        return self.adapter.execute_order(symbol=symbol, side=side, quantity=quantity, price=price, params=params)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        current_price: float,
        trigger_price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        if hasattr(self.adapter, "place_order"):
            return self.adapter.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                current_price=current_price,
                trigger_price=trigger_price,
                sl=sl,
                tp=tp,
                session_id=session_id,
                user_id=user_id if user_id is not None else self.user_id,
            )
        params = {
            "stop_loss": sl,
            "take_profit": tp,
            "session_id": session_id,
        }
        result = self.execute_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=current_price,
            params=params,
        )
        return result, {"status": result.get("status"), "order_id": result.get("order_id"), "mode": result.get("mode", "UNKNOWN"), "pnl": result.get("pnl", 0.0)}

    def get_balance(self, currency: str = "USDT") -> float:
        return self.adapter.get_balance(currency)

    def get_position(self, symbol: str) -> Dict[str, Any]:
        return self.adapter.get_position(symbol)

    def get_all_positions(self) -> list[Dict[str, Any]]:
        return self.adapter.get_all_positions()

    def check_portfolio_risk(self, current_equity: float = None) -> Dict[str, Any]:
        """
        Check Portfolio-Level Risk Limits (Circuit Breakers)
        """
        if hasattr(self.adapter, 'check_portfolio_risk'):
             # Pass user_id explicitly or adapter uses its own context?
             # Adapter init already has user_id
             return self.adapter.check_portfolio_risk(self.user_id, current_equity)
        return {"allowed": True, "reason": "Not implemented for this adapter"}
