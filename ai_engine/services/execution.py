import httpx
import asyncio
import hashlib
from typing import Dict, Any
from core.config import settings

class ExecutionService:
    def __init__(self):
        self.backend_url = settings.BACKEND_URL

    def evaluate_cost_budget(self, constraints: Dict[str, Any], quantity: float) -> Dict[str, Any]:
        micro = constraints.get("microstructure") or {}
        cost_policy = constraints.get("execution_cost_policy") or {}
        profiles = cost_policy.get("profiles") or {}
        profile_name = str(cost_policy.get("default_profile", "r120") or "r120")
        profile = profiles.get(profile_name) or {}

        fee_round_trip_bps = float(cost_policy.get("fee_round_trip_bps", 20.0) or 20.0)
        min_order_quantity = float(cost_policy.get("min_order_quantity", 0.01) or 0.01)
        variable_cost_cap_bps = float(profile.get("variable_cost_cap_bps", 22.0) or 22.0)

        spread_pct = float(micro.get("spread_pct", 0.0) or 0.0)
        spread_bps = spread_pct * 100.0
        est_slippage_bps = float(micro.get("estimated_slippage_bps", 0.0) or 0.0)
        estimated_variable_cost_bps = spread_bps + est_slippage_bps

        recommended_algo = self._recommend_execution_algo(micro)
        max_dev_map = profile.get("max_price_deviation_bps") or {}
        max_price_deviation_bps = float(max_dev_map.get(recommended_algo.lower(), 10.0) or 10.0)

        violations = []
        if quantity < min_order_quantity:
            violations.append("MIN_ORDER_QTY")
        if estimated_variable_cost_bps > variable_cost_cap_bps:
            violations.append("VARIABLE_COST_BUDGET_EXCEEDED")

        return {
            "allowed": len(violations) == 0,
            "violations": violations,
            "profile": profile_name,
            "fee_round_trip_bps": fee_round_trip_bps,
            "estimated": {
                "spread_bps": round(spread_bps, 2),
                "slippage_bps": round(est_slippage_bps, 2),
                "variable_cost_bps": round(estimated_variable_cost_bps, 2),
            },
            "caps": {
                "variable_cost_cap_bps": variable_cost_cap_bps,
                "max_price_deviation_bps": max_price_deviation_bps,
                "min_order_quantity": min_order_quantity,
            },
            "recommended_execution_algo": recommended_algo.upper(),
        }

    def _recommend_execution_algo(self, micro: Dict[str, Any]) -> str:
        spread_bps = float(micro.get("spread_pct", 0.0) or 0.0) * 100.0
        depth_imbalance = float(micro.get("depth_imbalance", 0.0) or 0.0)
        liquidity_tier = str(micro.get("liquidity_tier", "deep") or "deep").lower()
        if spread_bps <= 4.0 and liquidity_tier != "thin":
            return "limit"
        if spread_bps > 10.0 or depth_imbalance <= -0.5 or liquidity_tier == "thin":
            return "pov"
        return "twap"

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
        if execution_algo.upper() in {"TWAP", "POV"} and quantity > 0.001:
            return await self._execute_twap(
                action, symbol, quantity, price, confidence, 
                session_id, stop_loss, take_profit, order_type, trigger_condition,
                interval_seconds=2.0 if execution_algo.upper() == "POV" else 5.0,
                tag=execution_algo.lower(),
            )
            
        return await self._send_to_backend(
            action, symbol, quantity, price, confidence,
            session_id, stop_loss, take_profit, order_type, trigger_condition, "single"
        )

    async def _execute_twap(
        self, action, symbol, quantity, price, confidence,
        session_id, stop_loss, take_profit, order_type, trigger_condition,
        interval_seconds: float = 5.0,
        tag: str = "twap",
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
            print(f"[Execution] Order too small for {tag.upper()} (qty={quantity}, min_qty={min_qty:.4f}). Executing as STANDARD.")
            return await self._send_to_backend(
                action, symbol, quantity, price, confidence,
                session_id, stop_loss, take_profit, order_type, trigger_condition, f"{tag}-single"
            )
            
        chunk_size = round(quantity / chunks, 4)
        
        print(f"[Execution] Starting {tag.upper()}: {quantity} {symbol} split into {chunks} chunks of {chunk_size}")
        
        last_result = None
        filled_chunks = 0
        accepted_chunks = 0
        total_executed = 0.0
        
        for i in range(chunks):
            # For the last chunk, ensure we execute the exact remaining amount
            current_qty = round(quantity - total_executed, 4) if i == chunks - 1 else chunk_size
            
            result = await self._send_to_backend(
                action, symbol, current_qty, price, confidence,
                session_id, stop_loss, take_profit, order_type, trigger_condition, f"{tag}-{i+1}"
            )
            
            status = str(result.get("status") or "").upper()
            if status == "FILLED":
                filled_chunks += 1
                total_executed += current_qty
                last_result = result
            elif status == "ACCEPTED":
                accepted_chunks += 1
                last_result = result
            else:
                print(f"[Execution] {tag.upper()} Chunk {i+1} failed: {result.get('message')}")
                # For TWAP, if a chunk fails, we can choose to continue or abort. 
                # Here we continue to try filling the rest.
                
            if i < chunks - 1:
                await asyncio.sleep(interval_seconds)
                
        if filled_chunks == 0 and accepted_chunks == 0:
            return last_result or {"status": "error", "message": "All TWAP chunks failed"}

        if filled_chunks == 0 and accepted_chunks > 0:
            last_result["status"] = "ACCEPTED"
            last_result["message"] = f"{tag.upper()} Submitted. Accepted {accepted_chunks}/{chunks} chunks. Awaiting trigger/fill."
            return last_result

        status = "FILLED" if filled_chunks == chunks else "PARTIAL_FILLED"
        last_result["status"] = status
        last_result["message"] = f"{tag.upper()} Completed. Filled {filled_chunks}/{chunks} chunks. Total: {total_executed}"
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
