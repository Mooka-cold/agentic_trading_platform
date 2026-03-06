from abc import ABC, abstractmethod
from typing import Dict, Any

class ExecutionAdapter(ABC):
    """
    Abstract Base Class for Execution Adapters (Paper, Live, MCP, etc.)
    """
    
    @abstractmethod
    def execute_order(self, symbol: str, side: str, quantity: float, price: float = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute an order.
        Returns a standardized dict:
        {
            "order_id": str,
            "status": str, # FILLED, PENDING, REJECTED
            "executed_price": float,
            "fee": float,
            "timestamp": datetime
        }
        """
        pass

    @abstractmethod
    def get_balance(self, currency: str) -> float:
        """
        Get available balance for a currency.
        """
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Dict[str, Any]:
        """
        Get current open position for a symbol.
        Returns None if no position.
        """
        pass

    @abstractmethod
    def get_all_positions(self) -> list[Dict[str, Any]]:
        """
        Get all open positions.
        """
        pass
