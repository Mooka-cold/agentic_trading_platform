import math
from typing import Any, Dict, List
import httpx
from core.config import settings


class MarketIntelService:
    def __init__(self):
        self.backend_url = settings.BACKEND_URL

    async def fetch_ticker_depth(self, symbol: str, levels: int = 10) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"{self.backend_url}/api/v1/market/ticker",
                    params={"symbol": symbol, "levels": levels},
                )
            if res.status_code == 200:
                payload = res.json()
                if isinstance(payload, dict):
                    return payload
        except Exception:
            pass
        return {"symbol": symbol, "price": 0.0, "spread_pct": 0.0}

    async def fetch_klines(self, symbol: str, interval: str = "1m", limit: int = 120) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(
                    f"{self.backend_url}/api/v1/market/kline",
                    params={"symbol": symbol, "interval": interval, "limit": limit},
                )
            if res.status_code == 200:
                payload = res.json()
                if isinstance(payload, list):
                    return payload
        except Exception:
            pass
        return []

    def classify_regime(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(klines) < 20:
            return {
                "regime": "UNKNOWN",
                "trend_strength": 0.0,
                "volatility": 0.0,
                "quality": "low_sample",
            }
        closes = [float(k.get("close", 0.0) or 0.0) for k in klines if k.get("close") is not None]
        if len(closes) < 20:
            return {
                "regime": "UNKNOWN",
                "trend_strength": 0.0,
                "volatility": 0.0,
                "quality": "low_sample",
            }
        rets = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            cur = closes[i]
            if prev > 0:
                rets.append((cur - prev) / prev)
        if not rets:
            return {
                "regime": "UNKNOWN",
                "trend_strength": 0.0,
                "volatility": 0.0,
                "quality": "low_sample",
            }
        mean_ret = sum(rets) / len(rets)
        var = sum((r - mean_ret) ** 2 for r in rets) / len(rets)
        vol = math.sqrt(var)
        first = closes[0]
        last = closes[-1]
        trend = ((last - first) / first) if first > 0 else 0.0
        abs_trend = abs(trend)

        if vol >= 0.01:
            base = "RANGING_HIGH_VOL"
        elif vol <= 0.002:
            base = "RANGING_LOW_VOL"
        else:
            base = "RANGING"

        if abs_trend >= 0.02 and vol > 0:
            base = "TRENDING_UP" if trend > 0 else "TRENDING_DOWN"

        return {
            "regime": base,
            "trend_strength": round(abs_trend, 6),
            "volatility": round(vol, 6),
            "price_change_pct": round(trend * 100, 4),
            "quality": "ok",
        }

    def build_microstructure_snapshot(self, ticker_depth: Dict[str, Any], desired_notional: float) -> Dict[str, Any]:
        spread_pct = float(ticker_depth.get("spread_pct", 0.0) or 0.0)
        bid_depth_notional = float(ticker_depth.get("bid_depth_notional", 0.0) or 0.0)
        ask_depth_notional = float(ticker_depth.get("ask_depth_notional", 0.0) or 0.0)
        depth_imbalance = float(ticker_depth.get("depth_imbalance", 0.0) or 0.0)
        executable_notional = max(1e-6, min(bid_depth_notional, ask_depth_notional))
        slippage_bps = (desired_notional / executable_notional) * 10000.0
        liquidity_tier = "deep"
        if executable_notional < 250000:
            liquidity_tier = "thin"
        elif executable_notional < 1500000:
            liquidity_tier = "medium"
        return {
            "spread_pct": spread_pct,
            "bid_depth_notional": bid_depth_notional,
            "ask_depth_notional": ask_depth_notional,
            "depth_imbalance": depth_imbalance,
            "estimated_slippage_bps": round(slippage_bps, 2),
            "liquidity_tier": liquidity_tier,
        }

    def build_execution_constraints(self, regime: Dict[str, Any], micro: Dict[str, Any]) -> Dict[str, Any]:
        preferred_order_type = "MARKET"
        if micro.get("estimated_slippage_bps", 0.0) >= 20 or micro.get("spread_pct", 0.0) >= 0.08:
            preferred_order_type = "LIMIT"
            
        execution_algo = "STANDARD"
        if micro.get("estimated_slippage_bps", 0.0) >= 200 or micro.get("liquidity_tier") == "thin":
            execution_algo = "TWAP"
            
        rr_floor = 1.5
        if regime.get("regime") in {"TRENDING_UP", "TRENDING_DOWN"}:
            rr_floor = 1.35
        if micro.get("liquidity_tier") == "thin":
            rr_floor = 1.6
        gate_policy = {
            "review_only": {
                "qty_mult": 0.2 if micro.get("liquidity_tier") == "thin" else 0.25,
                "sl_widen_mult": 1.4 if regime.get("regime") in {"TRENDING_UP", "TRENDING_DOWN"} else 1.3,
            },
            "risk_reduced": {
                "qty_mult": 0.4 if micro.get("liquidity_tier") == "thin" else 0.5,
                "sl_widen_mult": 1.2,
            },
        }
        return {
            "preferred_order_type": preferred_order_type,
            "execution_algo": execution_algo,
            "rr_floor": rr_floor,
            "gate_policy": gate_policy,
        }

    def build_hedge_context(self, base_symbol: str, hedge_symbol: str, base_klines: List[Dict[str, Any]], hedge_klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(base_klines) < 30 or len(hedge_klines) < 30:
            return {
                "enabled": False,
                "base_symbol": base_symbol,
                "hedge_symbol": hedge_symbol,
                "reason": "insufficient_kline_history",
            }
        base_closes = [float(k.get("close", 0.0) or 0.0) for k in base_klines[-60:]]
        hedge_closes = [float(k.get("close", 0.0) or 0.0) for k in hedge_klines[-60:]]
        n = min(len(base_closes), len(hedge_closes))
        if n < 20:
            return {
                "enabled": False,
                "base_symbol": base_symbol,
                "hedge_symbol": hedge_symbol,
                "reason": "insufficient_overlap",
            }
        x = base_closes[-n:]
        y = hedge_closes[-n:]
        x_ret = []
        y_ret = []
        for i in range(1, n):
            if x[i - 1] > 0 and y[i - 1] > 0:
                x_ret.append((x[i] - x[i - 1]) / x[i - 1])
                y_ret.append((y[i] - y[i - 1]) / y[i - 1])
        m = min(len(x_ret), len(y_ret))
        if m < 10:
            return {
                "enabled": False,
                "base_symbol": base_symbol,
                "hedge_symbol": hedge_symbol,
                "reason": "insufficient_returns",
            }
        x_ret = x_ret[-m:]
        y_ret = y_ret[-m:]
        mean_x = sum(x_ret) / m
        mean_y = sum(y_ret) / m
        cov = sum((x_ret[i] - mean_x) * (y_ret[i] - mean_y) for i in range(m)) / m
        var_x = sum((r - mean_x) ** 2 for r in x_ret) / m
        var_y = sum((r - mean_y) ** 2 for r in y_ret) / m
        if var_x <= 0 or var_y <= 0:
            corr = 0.0
        else:
            corr = cov / math.sqrt(var_x * var_y)
        hedge_ratio = 1.0
        if var_y > 0:
            hedge_ratio = abs(cov / var_y)
        enabled = abs(corr) >= 0.45
        return {
            "enabled": enabled,
            "base_symbol": base_symbol,
            "hedge_symbol": hedge_symbol,
            "corr": round(corr, 4),
            "hedge_ratio": round(max(0.1, min(3.0, hedge_ratio)), 4),
        }

    def build_portfolio_context(self, account_balance: float, positions: List[Dict[str, Any]], mark_price: float) -> Dict[str, Any]:
        gross_notional = 0.0
        for p in positions:
            size = float(p.get("size", p.get("quantity", 0.0)) or 0.0)
            entry = float(p.get("entry_price", mark_price) or mark_price or 0.0)
            gross_notional += abs(size * entry)
        leverage = gross_notional / account_balance if account_balance > 0 else 0.0
        risk_mode = "normal"
        if leverage >= 2.0:
            risk_mode = "defensive"
        if leverage >= 3.0:
            risk_mode = "risk_off"
        return {
            "gross_notional": round(gross_notional, 2),
            "implied_leverage": round(leverage, 4),
            "risk_mode": risk_mode,
            "position_count": len(positions),
        }


market_intel_service = MarketIntelService()
