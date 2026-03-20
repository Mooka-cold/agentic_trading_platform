from typing import Dict, Any
from sqlalchemy.orm import Session
from app.services.execution.interfaces import ExecutionAdapter
from app.services.paper_trading import PaperTradingService, PaperPosition # Import models from service file

class PaperTradingAdapter(ExecutionAdapter):
    def __init__(self, db: Session, user_id: int = None):
        self.service = PaperTradingService(db)
        self.user_id = user_id
        # Important: Pass user_id to service if service methods need it, but service methods usually take user_id as arg.
        # However, for PaperTradingService methods like execute_market_order, they use self.get_or_create_account(user_id=None) which defaults to limit 1.
        # We should probably fix PaperTradingService to use self.user_id if passed in init?
        # But PaperTradingService init only takes db.
        # Let's ensure adapter passes user_id to service calls where possible.
        
    def get_order_history(self, user_id: int = None, limit: int = 20) -> list[Dict[str, Any]]:
        # This method is not in ExecutionAdapter interface yet, but useful for API
        orders = self.service.get_order_history(user_id or self.user_id, limit)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": o.side,
                "type": o.type,
                "intent": getattr(o, "intent", "MARKET"), # Use getattr to avoid attribute error if model not reloaded
                "price": float(o.price) if o.price else None,
                "quantity": float(o.quantity),
                "status": o.status,
                "pnl": float(o.pnl) if o.pnl is not None else None,
                "session_id": o.session_id,
                "created_at": o.created_at,
                "filled_at": o.filled_at
            }
            for o in orders
        ]

    def execute_order(self, symbol: str, side: str, quantity: float, price: float = None, type: str = "MARKET", params: dict = None) -> Dict[str, Any]:
        """
        Execute paper order via service.
        Supports passing order_book for slippage simulation if provided in params.
        """
        try:
            sl = params.get("stop_loss") if params else None
            tp = params.get("take_profit") if params else None
            session_id = params.get("session_id") if params else None
            order_book = params.get("order_book") if params else None

            order, exec_info = self.service.execute_market_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                current_price=price,
                sl=sl,
                tp=tp,
                session_id=session_id,
                order_book=order_book,
                user_id=self.user_id
            )
            
            return {
                "order_id": str(order.id),
                "status": order.status,
                "executed_price": float(order.price),
                "fee": 0.0, # No fee in simple paper trading yet
                "timestamp": order.filled_at,
                "pnl": exec_info["pnl"],
                "closed_session_id": exec_info["closed_session_id"],
                "mode": exec_info["mode"],
                "intent": exec_info["intent"]
            }
        except Exception as e:
            raise e

    def get_balance(self, currency: str = "USDT") -> float:
        account = self.service.get_or_create_account(self.user_id)
        # Assuming account has balance in base currency (USDT)
        # If we support multi-currency, we need to filter
        return float(account.balance)

    def get_position(self, symbol: str) -> Dict[str, Any]:
        """
        Get current open position for a symbol.
        Returns None if no position.
        """
        positions = self.service.get_open_positions(self.user_id)
        for p in positions:
            if p.symbol == symbol:
                return {
                    "symbol": p.symbol,
                    "side": p.side,
                    "size": float(p.size),
                    "entry_price": float(p.entry_price),
                    "opened_at": p.opened_at
                }
        return None

    def get_all_positions(self) -> list[Dict[str, Any]]:
        positions = self.service.get_open_positions(self.user_id)
        return [
            {
                "symbol": p.symbol,
                "side": p.side,
                "size": float(p.size),
                "entry_price": float(p.entry_price),
                "opened_at": p.opened_at
            }
            for p in positions
        ]

    def check_portfolio_risk(self, user_id: int, current_equity: float = None) -> dict:
        return self.service.check_portfolio_risk(user_id, current_equity) 
