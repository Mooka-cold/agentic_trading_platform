import asyncio
import json
import httpx
import yaml
from pathlib import Path
from datetime import datetime
from redis import Redis  # Fix NameError
from agents.base import BaseAgent
from model.state import AgentState, MarketData, StrategyProposal, AnalystOutput, RiskVerdict, SentimentOutput, TrendFollowerOutput, MeanReversionOutput, VolatilityHunterOutput, NewsInterpretationOutput
from services.market_data import market_data_service
from services.memory import memory_service
from services.execution import execution_service
from services.sentiment import sentiment_service
from services.risk_checks import compute_trade_metrics, get_missing_proposal_fields, build_fix_suggestions
from core.config import settings

# Lazy import for services to avoid circular deps or init issues
# from services.market_data import market_data_service 
# from services.memory import memory_service
# from services.execution import execution_service

class Analyst(BaseAgent):
    def __init__(self):
        super().__init__("analyst", "The Analyst")

    async def _get_realtime_data(self, symbol: str) -> dict:
        """
        Fetch realtime indicators from Redis (written by Market Streamer).
        Returns dict with price, rsi, macd, etc.
        """
        try:
            # Redis key: market:BTC/USDT:realtime
            key = f"market:{symbol}:realtime"
            data = await self.redis_client.hgetall(key)
            
            if not data:
                return {}
                
            # Check freshness (TTL 5s)
            updated_at = float(data.get('updated_at', 0))
            if datetime.now().timestamp() - updated_at > 10: # Allow 10s lag
                print(f"[Analyst] Redis data stale ({updated_at}). Falling back.", flush=True)
                return {}
                
            return data
        except Exception as e:
            print(f"[Analyst] Redis fetch failed: {e}", flush=True)
            return {}

    async def run(self, state: AgentState) -> dict:
        from services.memory import memory_service
        session_id = state.session_id
        symbol = state.market_data.symbol
        
        # Check for Feedback Request (Loop)
        has_feedback_request = bool(state.analyst_feedback)
        
        if has_feedback_request:
            await self.think(f"Received question from Strategist: '{state.analyst_feedback}'", session_id)
            await self.think("Re-evaluating with focused lens...", session_id)
        else:
            await self.think(f"Fetching realtime market data for {symbol}...", session_id)
        
        # ... (Data Fetching logic stays same) ...
        # (For brevity, we assume data fetching is idempotent and fast enough to re-run)
        
        # 1. Fetch Comprehensive Market Snapshot (1m/5m Indicators)
        snapshot = market_data_service.get_full_snapshot(symbol)
        indicators = snapshot.get('indicators', {})
        
        # Parse Technicals
        price = snapshot.get('price', 0.0)
        volume = snapshot.get('volume', 0.0)
        rsi = indicators.get('rsi', 50.0)
        
        # MACD
        macd_data = indicators.get('macd', {})
        if isinstance(macd_data, dict):
            macd_val = macd_data.get('value', 0.0)
            macd_sig = macd_data.get('signal', 0.0)
            macd_hist = macd_data.get('hist', 0.0)
        else:
            macd_val = float(macd_data)
            macd_sig, macd_hist = 0.0, 0.0

        # Bollinger Bands
        bb_data = indicators.get('bb', {})
        bb_upper = bb_data.get('upper', 0.0)
        bb_lower = bb_data.get('lower', 0.0)
        
        # Volume Analysis (Simple MA)
        # We need volume MA to detect breakouts. 
        # Since snapshot might not have vol MA, we can infer from recent vol or just log raw vol.
        # For now, raw volume is passed.
        
        # 2. Fetch Multi-Timeframe Context (Trend Alignment)
        mtf_context = market_data_service.get_multi_timeframe_context(symbol)
        mtf_text = ""
        stale_warnings = []
        if "error" not in mtf_context:
            mtf_text = "### Multi-Timeframe Trend\n"
            for tf_label, tf_key in [("1H (Macro)", "1h (Trend)"), ("15M (Structure)", "15m (Structure)"), ("5M (Momentum)", "5m (Entry)")]:
                ctx = mtf_context.get(tf_key)
                if isinstance(ctx, dict):
                    if ctx.get("is_stale"):
                        stale_warnings.append(f"{tf_label} data is stale")
                    trend_val = ctx.get("trend", "N/A")
                    mtf_text += f"- {tf_label}: {trend_val} (Close: {ctx.get('close')}, RSI: {ctx.get('rsi')})\n"
                else:
                    mtf_text += f"- {tf_label}: {ctx}\n"
        else:
            mtf_text = "### Multi-Timeframe Trend\nData unavailable."

        # Check sub-agent data staleness
        if state.macro_report and "[DATA STALE" in str(state.macro_report.key_factors):
            stale_warnings.append("Macro data is stale (>24h)")
        if state.onchain_report and "[DATA STALE" in str(state.onchain_report.analysis):
            stale_warnings.append("On-Chain data is stale (>24h)")
        if state.sentiment_report and "[DATA STALE" in str(state.sentiment_report.raw_data):
            stale_warnings.append("Sentiment/Fear&Greed data is stale")

        stale_alert_text = ""
        if stale_warnings:
            stale_alert_text = "⚠️ **SYSTEM DATA STALE WARNING** ⚠️\nThe following data sources are out of date and may be unreliable:\n" + "\n".join([f"- {w}" for w in stale_warnings]) + "\n\n**INSTRUCTION**: You MUST reduce your confidence score and highlight these risks in your analysis. If multiple critical sources are stale, recommend NEUTRAL/NO TRADE.\n\n"

        # Construct Technical Context for LLM
        technical_text = (
            f"{stale_alert_text}"
            f"### Realtime Technicals (1m)\n"
            f"- Price: {price}\n"
            f"- Volume: {volume}\n"
            f"- RSI(14): {rsi:.2f}\n"
            f"- MACD: Value={macd_val:.4f}, Signal={macd_sig:.4f}, Hist={macd_hist:.4f}\n"
            f"- Bollinger: Upper={bb_upper:.2f}, Lower={bb_lower:.2f}\n"
            f"- EMAs: Fast(7)={indicators.get('ema', {}).get('fast', 0.0):.2f}, Slow(25)={indicators.get('ema', {}).get('slow', 0.0):.2f}\n\n"
            f"{mtf_text}"
        )
        
        await self.think(
            f"Technical Analysis Data Ready (RSI={rsi:.2f}, MACD Hist={macd_hist:.4f})", 
            session_id, 
            artifact={"technical_data": technical_text}
        )

        news_list = "Sentiment context unavailable."
        if state.sentiment_report:
            sentiment_score = state.sentiment_report.score
            drivers = ", ".join(state.sentiment_report.key_drivers) if state.sentiment_report.key_drivers else "None"
            sentiment_band = "NEUTRAL"
            if sentiment_score >= 0.5:
                sentiment_band = "POSITIVE"
            elif sentiment_score <= -0.5:
                sentiment_band = "NEGATIVE"
            news_list = (
                f"Sentiment Score: {sentiment_score:.2f} ({sentiment_band})\n"
                f"Summary: {state.sentiment_report.summary}\n"
                f"Key Drivers: {drivers}"
            )

        # --- Sub-Agent Execution ---
        await self.think("Engaging sub-agents (Trend, Reversion, Volatility)...", session_id)
        
        sub_agent_reports = "Sub-agents unavailable."
        try:
            # Parallel execution
            # Note: We pass the prompt_name to call_llm
            t_task = self.call_llm({"technical_data": technical_text}, TrendFollowerOutput, "analyst_trend")
            m_task = self.call_llm({"technical_data": technical_text}, MeanReversionOutput, "analyst_reversion")
            v_task = self.call_llm({"technical_data": technical_text}, VolatilityHunterOutput, "analyst_volatility")
            
            results = await asyncio.gather(t_task, m_task, v_task, return_exceptions=True)
            
            trend_res = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
            mean_res = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}
            vol_res = results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])}
            
            # Format sub-reports for Synthesis Prompt
            sub_agent_reports = (
                f"### 1. Trend Follower\n"
                f"- Signal: {trend_res.get('signal', 'N/A')}\n"
                f"- Structure: {trend_res.get('structure', 'N/A')}\n"
                f"- Key Level: {trend_res.get('key_level', 'N/A')}\n"
                f"- Reasoning: {trend_res.get('reasoning', 'N/A')}\n\n"
                
                f"### 2. Mean Reversionist\n"
                f"- Signal: {mean_res.get('signal', 'N/A')}\n"
                f"- Deviation: {mean_res.get('deviation_score', 0.0)}\n"
                f"- Target: {mean_res.get('target_price', 'N/A')}\n"
                f"- Reasoning: {mean_res.get('reasoning', 'N/A')}\n\n"
                
                f"### 3. Volatility Hunter\n"
                f"- Regime: {vol_res.get('regime', 'N/A')}\n"
                f"- Squeeze Score: {vol_res.get('sqz_score', 0.0)}\n"
                f"- Reasoning: {vol_res.get('reasoning', 'N/A')}\n"
            )
            
            await self.think(
                f"Sub-Agents Report: Trend={trend_res.get('signal')} | Reversion={mean_res.get('signal')} | Volatility={vol_res.get('regime')}",
                session_id,
                artifact={
                    "trend": trend_res,
                    "reversion": mean_res,
                    "volatility": vol_res
                }
            )
            
        except Exception as e:
            print(f"[Analyst] Sub-agents failed: {e}")
            await self.think(f"Sub-agents failed: {e}", session_id, log_type="error")

        # 3. Call LLM (Synthesis)
        try:
            # Handle Feedback Loop Prompt Injection
            user_instruction = ""
            if state.analyst_feedback:
                user_instruction = f"\n[URGENT QUERY FROM STRATEGIST] The strategist needs clarification: '{state.analyst_feedback}'. Please specifically address this in your reasoning and risk analysis."
            
            result = await self.call_llm(
                prompt_vars={
                    "news_list": news_list,
                    "technical_data": technical_text + user_instruction,
                    "sub_agent_reports": sub_agent_reports
                },
                output_model=AnalystOutput
            )

            # Result is a dict (parsed JSON)
            report = AnalystOutput(**result)
            
            await self.say(
                f"BIAS: {report.trading_bias}. {report.summary}", 
                session_id,
                artifact={
                    "bias": report.trading_bias,
                    "risk": report.key_risk,
                    "reasoning": report.reasoning
                }
            )
            
            # If this was a feedback loop, we MUST clear the feedback request to prevent infinite loop
            # BUT we can't return None for a field in dict update if we want to clear it?
            # LangGraph reducer: if right.analyst_feedback is None, it doesn't clear left.
            # We need a special signal or modify reducer.
            # OR we just rely on Strategist to not ask again.
            
            # Better: Strategist logic "if not state.analyst_feedback" ensures it only asks once.
            # But the state still has the old feedback string.
            # We should probably clear it.
            # Let's return explicit None if our reducer supports it? 
            # Our reducer: if right.analyst_feedback: left = right. 
            # It doesn't handle clearing.
            
            # Let's keep it simple: Analyst returns the report.
            # Strategist sees report. Strategist sees "I already asked".
            # Strategist proceeds.
            
            return {"analyst_report": report}
            
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            await self.think(f"Analysis failed: {str(e)}", session_id, log_type="error")
            print(f"[Analyst Error] {traceback_str}", flush=True)
            # Fallback
            return {}

