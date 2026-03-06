from typing import Dict, Any
from sqlalchemy.orm import Session
from app.services.execution.interfaces import ExecutionAdapter
from app.services.paper_trading import PaperTradingService, PaperPosition # Import models from service file

class PaperTradingAdapter(ExecutionAdapter):
    def __init__(self, db: Session, user_id: int = None):
        self.service = PaperTradingService(db)
        self.user_id = user_id

    def execute_order(self, symbol: str, side: str, quantity: float, price: float = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute order via PaperTradingService
        """
        try:
            # PaperTradingService currently only supports MARKET orders via execute_market_order
            # If price is provided, it's used as current market price for simulation
            # If it's a LIMIT order, we might need to enhance PaperTradingService later
            
            # For now, treat everything as MARKET order at `price`
            if not price:
                raise ValueError("Paper trading requires current price simulation")

            sl = params.get("stop_loss") if params else None
            tp = params.get("take_profit") if params else None
            session_id = params.get("session_id") if params else None

            order, exec_info = self.service.execute_market_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                current_price=price,
                sl=sl,
                tp=tp,
                session_id=session_id
            )
            
            return {
                "order_id": str(order.id),
                "status": "FILLED", # Paper trading fills instantly
                "executed_price": float(order.price),
                "fee": 0.0, # No fee in simple paper trading yet
                "timestamp": order.filled_at,
                "pnl": exec_info["pnl"],
                "closed_session_id": exec_info["closed_session_id"],
                "mode": exec_info["mode"]
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
