from collections import defaultdict
from typing import Dict, Any, Callable, List, Optional
from talipp.indicators import SMA, RSI, MACD, BB, EMA, Stoch

class IndicatorEngine:
    def __init__(self):
        # symbol -> { "sma_20": SMA(20), "rsi_14": RSI(14) }
        self.indicators: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.callbacks: List[Callable] = []

    def register_indicator(self, symbol: str, name: str, indicator_cls, **kwargs):
        """
        Register a new indicator for real-time calculation.
        """
        self.indicators[symbol][name] = indicator_cls(**kwargs)
        # print(f"Registered {name} for {symbol}")

    def on_tick(self, symbol: str, price: float):
        """
        Update indicators with new price.
        """
        symbol_inds = self.indicators[symbol]
        
        # 1. Update base indicators
        for name, indicator in symbol_inds.items():
            if hasattr(indicator, 'add'):
                indicator.add(price)
            
        # 2. Calculate derived metrics (e.g., crossovers)
        return self._calculate_derived(symbol, symbol_inds)

    def _calculate_derived(self, symbol: str, inds: Dict[str, Any]) -> Dict[str, Any]:
        """
        Logic for complex signals (e.g., Golden Cross, RSI Divergence)
        """
        signals = {}
        
        # RSI Overbought/Oversold
        if "rsi_14" in inds:
            rsi_val = inds["rsi_14"][-1] if len(inds["rsi_14"]) > 0 else None
            if rsi_val:
                if rsi_val > 70:
                    signals["RSI_STATUS"] = "OVERBOUGHT"
                elif rsi_val < 30:
                    signals["RSI_STATUS"] = "OVERSOLD"
                else:
                    signals["RSI_STATUS"] = "NEUTRAL"
                    
        # MACD Crossover
        if "macd" in inds:
            macd_val = inds["macd"][-1] if len(inds["macd"]) > 0 else None
            # MACD usually returns (macd, signal, hist) tuple or object
            # Talipp MACD returns a value object, let's assume it has .macd and .signal properties
            if macd_val:
                # Basic check (implementation depends on Talipp version specifics)
                if macd_val.macd > macd_val.signal:
                    signals["MACD_CROSS"] = "BULLISH"
                else:
                    signals["MACD_CROSS"] = "BEARISH"

        # Bollinger Bands Squeeze
        if "bb_20" in inds:
            bb_val = inds["bb_20"][-1] if len(inds["bb_20"]) > 0 else None
            if bb_val:
                bandwidth = (bb_val.ub - bb_val.lb) / bb_val.cb
                if bandwidth < 0.1: # Threshold for squeeze
                    signals["BB_STATUS"] = "SQUEEZE"

        return signals

    def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        """
        Get current values of all indicators for a symbol
        """
        snapshot = {}
        for name, ind in self.indicators[symbol].items():
            if len(ind) > 0:
                # Talipp indicators are list-like, last element is current value
                snapshot[name] = ind[-1]
        return snapshot
