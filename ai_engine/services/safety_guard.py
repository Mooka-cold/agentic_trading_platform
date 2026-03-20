from typing import Any, Dict


class SafetyGuardService:
    def evaluate(self, market_data: Dict[str, Any], micro: Dict[str, Any], portfolio: Dict[str, Any]) -> Dict[str, Any]:
        price = float(market_data.get("price", 0.0) or 0.0)
        spread_pct = float(micro.get("spread_pct", 0.0) or 0.0)
        slippage_bps = float(micro.get("estimated_slippage_bps", 0.0) or 0.0)
        leverage = float(portfolio.get("implied_leverage", 0.0) or 0.0)

        if price <= 0:
            return {"allowed": False, "reason": "invalid_price", "severity": "critical"}
        if spread_pct >= 2.0: # 极端价差才熔断，普通大价差交由 TWAP 处理
            return {"allowed": False, "reason": "spread_too_wide", "severity": "critical"}
        if leverage >= 4.0:
            return {"allowed": False, "reason": "portfolio_leverage_too_high", "severity": "critical"}
        
        # 滑点不再硬性熔断，而是转为 warning 提示执行引擎走分单
        if slippage_bps >= 200 or spread_pct >= 0.25:
            return {"allowed": True, "reason": "degraded_execution_twap_required", "severity": "warning"}
            
        return {"allowed": True, "reason": "normal", "severity": "info"}


safety_guard_service = SafetyGuardService()
