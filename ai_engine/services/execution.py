import httpx
import asyncio
import hashlib
from typing import Dict, Any
from core.config import settings

class ExecutionService:
    def __init__(self):
        self.backend_url = settings.BACKEND_URL

    async def execute_order(
        self,
        action: str,
        symbol: str,
        quantity: float,
        price: float,
        confidence: float,
        session_id: str = None,
        stop_loss: float = None,
        take_profit: float = None,
        order_type: str = "MARKET",
        trigger_condition: str = None,
        execution_algo: str = "STANDARD"
    ) -> Dict[str, Any]:
        """
        Send order execution request to Backend Trade API.
        If execution_algo is TWAP, split the order into smaller chunks.
        """
        if execution_algo == "TWAP" and quantity > 0.001:
            return await self._execute_twap(
                action, symbol, quantity, price, confidence, 
                session_id, stop_loss, take_profit, order_type, trigger_condition
            )
            
        return await self._send_to_backend(
            action, symbol, quantity, price, confidence,
            session_id, stop_loss, take_profit, order_type, trigger_condition, "single"
        )

    async def _execute_twap(
        self, action, symbol, quantity, price, confidence,
        session_id, stop_loss, take_profit, order_type, trigger_condition
    ) -> Dict[str, Any]:
        """
        Simple TWAP: split into multiple chunks, execute every 5 seconds.
        Ensures each chunk meets exchange minimum notional (e.g., $10-$20 equivalent).
        """
        # Calculate minimum chunk size based on a safe minimum notional (e.g., $50 to be safe on fees and exchange limits)
        # Using current price to estimate how much quantity equals $50
        min_notional = 50.0 
        min_qty = min_notional / price if price > 0 else 0.005
        
        # Max 10 chunks, but also constrained by min_qty per chunk
        max_possible_chunks = max(1, int(quantity / min_qty))
        chunks = min(10, max_possible_chunks)
        
        # If order is too small to even split safely, just execute as a single chunk
        if chunks <= 1:
            print(f"[Execution] Order too small for TWAP (qty={quantity}, min_qty={min_qty:.4f}). Executing as STANDARD.")
            return await self._send_to_backend(
                action, symbol, quantity, price, confidence,
                session_id, stop_loss, take_profit, order_type, trigger_condition, "twap-single"
            )
            
        chunk_size = round(quantity / chunks, 4)
        
        print(f"[Execution] Starting TWAP: {quantity} {symbol} split into {chunks} chunks of {chunk_size}")
        
        last_result = None
        successful_chunks = 0
        total_executed = 0.0
        
        for i in range(chunks):
            # For the last chunk, ensure we execute the exact remaining amount
            current_qty = round(quantity - total_executed, 4) if i == chunks - 1 else chunk_size
            
            result = await self._send_to_backend(
                action, symbol, current_qty, price, confidence,
                session_id, stop_loss, take_profit, order_type, trigger_condition, f"twap-{i+1}"
            )
            
            if result.get("status") == "FILLED" or result.get("status") == "ACCEPTED":
                successful_chunks += 1
                total_executed += current_qty
                last_result = result
            else:
                print(f"[Execution] TWAP Chunk {i+1} failed: {result.get('message')}")
                # For TWAP, if a chunk fails, we can choose to continue or abort. 
                # Here we continue to try filling the rest.
                
            if i < chunks - 1:
                await asyncio.sleep(5.0) # Wait 5 seconds between chunks
                
        if successful_chunks == 0:
            return last_result or {"status": "error", "message": "All TWAP chunks failed"}
            
        # Return the last successful result, but modified to reflect partial/full fill
        status = "FILLED" if successful_chunks == chunks else "PARTIAL_FILLED"
        last_result["status"] = status
        last_result["message"] = f"TWAP Completed. Executed {successful_chunks}/{chunks} chunks. Total: {total_executed}"
        return last_result

    async def _send_to_backend(
        self,
        action: str,
        symbol: str,
        quantity: float,
        price: float,
        confidence: float,
        session_id: str = None,
        stop_loss: float = None,
        take_profit: float = None,
        order_type: str = "MARKET",
        trigger_condition: str = None,
        idempotency_suffix: str = "single"
    ) -> Dict[str, Any]:
        idempotency_raw = f"{session_id}|{action}|{symbol}|{quantity}|{price}|{order_type}|{trigger_condition or ''}|{idempotency_suffix}"
        idempotency_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()
        payload = {
            "action": action,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "confidence": confidence,
            "session_id": session_id,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "order_type": order_type,
            "trigger_condition": trigger_condition,
            "idempotency_key": idempotency_key
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
