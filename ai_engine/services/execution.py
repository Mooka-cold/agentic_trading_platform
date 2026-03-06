import httpx
from typing import Dict, Any
from core.config import settings

class ExecutionService:
    def __init__(self):
        self.backend_url = settings.BACKEND_URL

    async def execute_order(self, action: str, symbol: str, quantity: float, price: float, confidence: float, session_id: str = None, stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """
        Send order execution request to Backend Trade API.
        """
        payload = {
            "action": action,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "confidence": confidence,
            "session_id": session_id,
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.backend_url}/api/v1/trade/execute", json=payload)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "status": "error", 
                        "message": f"Backend Error {response.status_code}: {response.text}",
                        "executed_price": 0.0,
                        "new_balance": 0.0,
                        "mode": "UNKNOWN"
                    }
                    
        except httpx.RequestError as e:
            return {
                "status": "error", 
                "message": f"Connection Failed: {str(e)}",
                "executed_price": 0.0,
                "new_balance": 0.0
            }
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Execution Exception: {str(e)}",
                "executed_price": 0.0,
                "new_balance": 0.0
            }

execution_service = ExecutionService()
