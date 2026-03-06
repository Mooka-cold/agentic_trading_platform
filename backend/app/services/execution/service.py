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
        elif self.mode == "LIVE":
            # self.adapter = LiveTradingAdapter(db, user_id)
            raise NotImplementedError("Live Trading not yet implemented")
        else:
            raise ValueError(f"Unknown TRADING_MODE: {self.mode}")

    def execute_order(self, symbol: str, side: str, quantity: float, price: float = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Route order to appropriate adapter
        """
        print(f"[ExecutionService] Routing {side} {quantity} {symbol} to {self.mode} Adapter")
        return self.adapter.execute_order(symbol, side, quantity, price, params)

    def get_balance(self, currency: str = "USDT") -> float:
        return self.adapter.get_balance(currency)

    def get_position(self, symbol: str) -> Dict[str, Any]:
        return self.adapter.get_position(symbol)

    def get_all_positions(self) -> list[Dict[str, Any]]:
        return self.adapter.get_all_positions()
