import json
import asyncio
from typing import Dict, Any, List
from agents.base import BaseAgent
from model.state import AgentState, MacroOutput
from services.macro_data import macro_data_service

class MacroAgent(BaseAgent):
    def __init__(self):
        super().__init__("macro", "The Macro Economist")

    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        
        await self.think("Fetching global macro data from Data Service...", session_id)
        
        try:
            # Fetch from Backend API via Service
            data = await macro_data_service.get_macro_metrics()
            
            if not data:
                await self.think("Macro data unavailable. Triggering update...", session_id)
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
                    
            dxy_ts = data.get("DXY", {}).get("timestamp")
            if check_staleness(dxy_ts):
                is_stale = True
                await self.think("⚠️ WARNING: Macro data is STALE (>24h old). The Data Service might be failing.", session_id, log_type="error")

            # Analyze Regime
            regime, risk_score, reasons = self._analyze_regime(data)
            
            if is_stale:
                reasons.insert(0, "[DATA STALE - PROCEED WITH CAUTION]")
            
            await self.say(
                f"MACRO REGIME: {regime} (Risk Score: {risk_score})",
                session_id,
                artifact={
                    "regime": regime,
                    "risk_score": risk_score,
                    "reasons": reasons,
                    "data": data
                }
            )
            
            output = MacroOutput(
                regime=regime,
                risk_score=risk_score,
                key_factors=reasons,
                data_summary=data
            )
            
            return {"macro_report": output}
            
        except Exception as e:
            await self.think(f"Macro analysis failed: {e}", session_id, log_type="error")
            import traceback
            traceback.print_exc()
            return {}

    def _analyze_regime(self, data: Dict[str, Any]):
        risk_score = 0
        reasons = []
        
        # Helper to get value safely
        def get_val(key, field="price"):
            return data.get(key, {}).get(field)
            
        # 1. DXY Check (Assuming we have change_24h or trend in DB, 
        # but currently DB only stores value. We need history for trend.
        # For MVP, we can't calculate trend from single snapshot.
        # However, Backend Service crawler calculates change/trend before saving? 
        # No, DB model only has 'value'. 
        # Ideally, we should fetch history or store 'trend' in DB.
        # For now, let's assume 'value' is what we have. 
        # We can compare against hard thresholds or move 'trend' calculation to Backend Service?
        # Let's use simple thresholds for MVP.)
        
        dxy = get_val("DXY")
        if dxy and dxy > 104: # Strong Dollar threshold
            risk_score += 1
            reasons.append(f"Strong DXY ({dxy}) puts pressure on risk assets.")
            
        # 2. Bond Yield Check
        us10y = get_val("US_10Y_BOND")
        if us10y and us10y > 4.2: # High Yield threshold
            risk_score += 1
            reasons.append(f"High 10Y Yields ({us10y}%) reduce liquidity.")
            
        # 3. F&G Contrarian
        fng = get_val("FEAR_AND_GREED")
        if fng:
            if fng < 20:
                risk_score -= 1 # Buy signal
                reasons.append(f"Extreme Fear ({fng}) suggests potential bottom.")
            elif fng > 80:
                risk_score += 1 # Sell signal
                reasons.append(f"Extreme Greed ({fng}) suggests overheating.")
            
        # 4. VIX Check
        vix = get_val("VIX")
        if vix and vix > 20:
            risk_score += 1
            reasons.append(f"VIX is high ({vix}), indicating market fear.")
            
        regime = "NEUTRAL"
        if risk_score >= 2: regime = "RISK_OFF"
        elif risk_score <= -1: regime = "RISK_ON"
        
        return regime, risk_score, reasons

