from agents.base import BaseAgent
from model.state import AgentState, OnChainOutput
from services.onchain_data import onchain_data_service

class OnChainAgent(BaseAgent):
    def __init__(self):
        super().__init__("onchain", "The On-Chain Detective")

    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        # Extract base symbol (BTC/USDT -> BTC)
        symbol = state.market_data.symbol.split("/")[0]
        
        await self.think(f"Investigating On-Chain data for {symbol}...", session_id)
        
        data = await onchain_data_service.get_onchain_metrics(symbol)
        
        if not data:
            await self.think("No On-Chain data available.", session_id)
            return {}
            
        # Check Data Freshness
        is_stale = False
        import datetime
        from dateutil import parser
        
        # Helper to check timestamp
        def check_staleness(timestamp_str, max_hours=24):
            if not timestamp_str: return False
            try:
                dt = parser.parse(timestamp_str)
                # handle timezone awareness
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                now = datetime.datetime.now(datetime.timezone.utc)
                return (now - dt).total_seconds() > max_hours * 3600
            except:
                return False
                
        ls_timestamp = data.get("LS_RATIO", {}).get("timestamp")
        oi_timestamp = data.get("OI", {}).get("timestamp")
        
        if check_staleness(ls_timestamp) or check_staleness(oi_timestamp):
            is_stale = True
            await self.think("⚠️ WARNING: On-Chain data is STALE (>24h old). The API source might be failing.", session_id, log_type="error")
            
        # Analysis Logic
        score = 0
        analysis = []
        
        if is_stale:
            analysis.append("[DATA STALE - PROCEED WITH CAUTION]")
        
        # 1. LS Ratio (Sentiment)
        ls_ratio = data.get("LS_RATIO", {}).get("value")
        if ls_ratio:
            if ls_ratio > 2.5:
                score -= 2 # Extreme Longs -> Bearish
                analysis.append(f"High LS Ratio ({ls_ratio:.2f}) indicates overcrowded longs (Long Squeeze Risk).")
            elif ls_ratio > 1.5:
                score -= 1
                analysis.append(f"Elevated LS Ratio ({ls_ratio:.2f}).")
            elif ls_ratio < 0.7:
                score += 2 # Extreme Shorts -> Bullish
                analysis.append(f"Low LS Ratio ({ls_ratio:.2f}) indicates overcrowded shorts (Short Squeeze Potential).")
            else:
                analysis.append(f"LS Ratio ({ls_ratio:.2f}) is neutral.")
                
        # 2. OI (Open Interest)
        oi = data.get("OI", {}).get("value")
        if oi:
            # Simple heuristic: High OI + Neutral/Bearish Price -> Volatility Incoming
            analysis.append(f"Open Interest is ${oi/1e9:.2f}B.")
            
        signal = "NEUTRAL"
        if score >= 1: signal = "BULLISH"
        elif score <= -1: signal = "BEARISH"
        
        output = OnChainOutput(
            signal=signal,
            score=score,
            metrics=data,
            analysis="; ".join(analysis)
        )
        
        await self.say(
            f"ON-CHAIN: {signal} (Score: {score}). {output.analysis}",
            session_id,
            artifact=output.dict()
        )
        
        return {"onchain_report": output}
