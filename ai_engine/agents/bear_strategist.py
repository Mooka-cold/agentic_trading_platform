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

class BearStrategist(BaseAgent):
    def __init__(self):
        super().__init__("bear_strategist", "The Bear Strategist")

    async def run(self, state: AgentState) -> dict:
        from services.execution import execution_service
        session_id = state.session_id
        symbol = state.market_data.symbol
        
        if not state.analyst_report:
            await self.think("No analyst report found. Skipping.", session_id)
            return {}

        report = state.analyst_report
        # If we have a new report answering our question, acknowledge it
        if state.analyst_feedback and "clarification" in report.reasoning.lower(): # Heuristic check
             await self.think(f"Received clarification from Analyst: {report.summary}", session_id)
        
        await self.think(f"Reviewing Analyst's bias: {report.trading_bias}...", session_id)
        
        # Prepare context for LLM
        # Use full Analyst Reasoning + Sentiment Report
        sentiment_context = "Neutral"
        sentiment_score = 0.0
        if state.sentiment_report:
            sentiment_score = state.sentiment_report.score
            sentiment_context = (
                f"Score: {sentiment_score:.2f}\n"
                f"Summary: {state.sentiment_report.summary}\n"
                f"Drivers: {', '.join(state.sentiment_report.key_drivers)}"
            )

        # --- 1. Sentiment-Technical Integration (Weighted Mechanism) ---
        sentiment_instruction = ""
        # Check for Strong Trend from sub-agents to disable contrarian logic
        is_strong_trend = False
        if "STRONG" in report.reasoning.upper() or "ADX > 25" in report.reasoning.upper():
            is_strong_trend = True

        if sentiment_score > 0.8:
            if is_strong_trend:
                sentiment_instruction = "\n[SENTIMENT NOTE] Extreme Greed, but Strong Trend detected. DO NOT fade the trend."
            else:
                sentiment_instruction = (
                    "\n[SENTIMENT OVERRIDE] EXTREME GREED DETECTED (>0.8). "
                    "Market is likely overextended. Treat 'Neutral' technicals as potential TOP signals. "
                    "Tighten stops on Longs. Look for Bearish Divergence."
                )
        elif sentiment_score < -0.8:
            if is_strong_trend:
                sentiment_instruction = "\n[SENTIMENT NOTE] Extreme Fear, but Strong Downtrend detected. DO NOT fade the trend."
            else:
                sentiment_instruction = (
                    "\n[SENTIMENT OVERRIDE] EXTREME FEAR DETECTED (<-0.8). "
                    "Market is likely oversold. Treat 'Neutral' technicals as potential BOTTOM signals. "
                    "Look for Bullish Reversal (RSI Divergence). Consider 'Buy the Dip' if support holds."
                )
        # -------------------------------------------------------------

        # --- 2. Macro Regime Integration ---
        macro_context = "Neutral"
        if state.macro_report:
            m = state.macro_report
            macro_context = f"{m.regime} (Score: {m.risk_score})"
            # Override Instruction based on Regime
            if m.regime == "RISK_OFF":
                sentiment_instruction += "\n[MACRO OVERRIDE] GLOBAL RISK OFF DETECTED. Reduce position size by 50%. Avoid Longs unless technicals are perfect."
            elif m.regime == "RISK_ON":
                sentiment_instruction += "\n[MACRO OVERRIDE] GLOBAL RISK ON. Favorable for Longs. Look for dips to buy."
        
        # --- 3. On-Chain Integration ---
        onchain_context = "Neutral"
        if state.onchain_report:
            oc = state.onchain_report
            onchain_context = f"{oc.signal} (Score: {oc.score})"
            
            # Signal Convergence Check
            if oc.signal == "BEARISH" and "BEARISH" in report.trading_bias:
                sentiment_instruction += "\n[CONVERGENCE] On-Chain and Technicals align BEARISH. High conviction Short."
            elif oc.signal == "BULLISH" and "BULLISH" in report.trading_bias:
                sentiment_instruction += "\n[CONVERGENCE] On-Chain and Technicals align BULLISH. High conviction Long."
            elif oc.signal != "NEUTRAL" and oc.signal not in report.trading_bias:
                sentiment_instruction += f"\n[DIVERGENCE] On-Chain is {oc.signal} but Technicals are {report.trading_bias}. Reduce position size and use tighter stops."
        # -----------------------------------

        market_summary = (
            f"Price: {state.market_data.price}\n"
            f"Technical Context: {report.reasoning}\n"
            f"Sentiment Context: {sentiment_context}\n"
            f"Macro Context: {macro_context}\n"
            f"On-Chain Context: {onchain_context}{sentiment_instruction}\n"
            f"Risk Context: {report.key_risk}"
        )
        regime_context = json.dumps(state.market_regime or {"regime": "UNKNOWN"}, ensure_ascii=False)
        microstructure_context = json.dumps(state.microstructure or {}, ensure_ascii=False)
        portfolio_context = json.dumps(state.portfolio_context or {}, ensure_ascii=False)
        execution_constraints = json.dumps(state.execution_constraints or {}, ensure_ascii=False)
        
        # Log Input Context for Strategist Traceability
        await self.think(
            "Strategist Input Context Prepared", 
            session_id, 
            artifact={
                "market_summary": market_summary,
                "analyst_bias": report.trading_bias,
                "regime_context": regime_context,
                "microstructure_context": microstructure_context,
                "portfolio_context": portfolio_context,
                "execution_constraints": execution_constraints,
                "unresolved_todos": state.unresolved_todos
            }
        )
        
        # Retrieve Memory
        await self.think("Recalling past experiences and learned rules...", session_id)
        try:
            # 1. Contextual Insights (Similar market conditions)
            insights = memory_service.retrieve_insights(
                query=f"Market Condition: {report.summary}",
                limit=3
            )
            insight_context = "\n".join([f"- {i}" for i in insights]) if insights else "No relevant past insights found."
            
            # 2. Hard-Learned Rules (From FINAL synthesis)
            learned_rules = memory_service.retrieve_learned_rules(limit=3)
            rule_context = "\n".join([f"- [RULE] {r}" for r in learned_rules]) if learned_rules else "No specific learned rules yet."
            
            memory_context = f"### Past Insights (Contextual)\n{insight_context}\n\n### Iron Rules (From Post-Mortem)\n{rule_context}"
            
        except Exception as e:
            memory_context = f"Error retrieving memory: {e}"

        # --- PRE-CALCULATE RISK PARAMETERS (Hybrid Architecture) ---
        # Instead of letting LLM guess, we calculate ATR-based SL/TP here.
        # 1. Get ATR (Assuming it's in indicators, else estimate from volatility)
        # Note: MarketData model has indicators dict.
        # We need to robustly fetch ATR.
        atr_val = state.market_data.indicators.get('atr', 0.0)
        current_price = state.market_data.price
        
        # Fallback if ATR is missing: Use 2% of price
        atr_source = "ATR(14)"
        if atr_val <= 0:
            atr_val = current_price * 0.02
            atr_source = "Fallback(2%)"
            
        # Calculate Suggested SL/TP for both Directions
        # Rule: SL = 2 * ATR, TP = 3 * ATR (1.5 R/R)
        sl_dist = 2.0 * atr_val
        tp_dist = 3.0 * atr_val
        
        long_sl = current_price - sl_dist
        long_tp = current_price + tp_dist
        short_sl = current_price + sl_dist
        short_tp = current_price - tp_dist
        
        # Format for Prompt
        risk_calc_context = (
            f"### RISK PARAMETERS (PRE-CALCULATED)\n"
            f"- Current Price: {current_price:.2f}\n"
            f"- Volatility ({atr_source}): {atr_val:.2f}\n"
            f"- Suggested LONG: Entry={current_price:.2f}, SL={long_sl:.2f}, TP={long_tp:.2f}\n"
            f"- Suggested SHORT: Entry={current_price:.2f}, SL={short_sl:.2f}, TP={short_tp:.2f}\n"
            f"**INSTRUCTION**: You CAN use these exact values to ensure risk compliance. If you deviate, explain why."
        )
        
        await self.think(f"Pre-calculated Risk Params: ATR={atr_val:.2f} ({atr_source})", session_id)
        # -----------------------------------------------------------

        await self.think("Formulating trading plan...", session_id)
        
        user_strategy_config = (
            "Strategy: Trend Following. Timeframe: 1H/15M. Risk: 1% per trade.\n"
            "RULES:\n"
            "1. Do NOT trade against the 1H Trend (e.g. No Shorts if 1H is Bullish).\n"
            "2. If 1H Trend opposes current position, CLOSE immediately.\n"
            "3. If Rejection occurred previously, fix the specific issue (e.g. add SL/TP)."
        )
        review_feedback = "None"
        if state.review_feedback:
            review_feedback = json.dumps(state.review_feedback, ensure_ascii=False)
            await self.think(f"Revision round {state.strategy_revision_round}: applying reviewer feedback.", session_id)

        # Format Positions
        positions_str = "None"
        if state.positions:
            my_pos = [p for p in state.positions if p['symbol'] == symbol]
            if my_pos:
                # Provide detailed position info for LLM
                positions_str = json.dumps(my_pos, default=str)

        # 3. Handle Neutral Bias with Open Position (Optimization)
        # If bias is NEUTRAL and we have a profitable position, suggest trailing stop or partial close
        if report.trading_bias == "NEUTRAL" and positions_str != "None":
            await self.think("Bias is NEUTRAL but Position exists. Evaluating hold management...", session_id)
            # We inject a specific instruction into the prompt
            memory_context += "\n\n[CRITICAL INSTRUCTION] The market is NEUTRAL but we have an open position. Prioritize 'HOLD' with a tightened Stop Loss (Trailing Stop) or 'PARTIAL_CLOSE' to lock in profits. Do NOT Panic Sell unless indicators are clearly bearish."

        # 4. Check if we need more info (Loop)
        # Simple heuristic: If confidence is low (<0.4) and we haven't asked yet.
        # But Strategist LLM output model doesn't support "ASK".
        # We can either change the model or use a heuristic here.
        # Let's inject a prompt instruction: "If you are unsure, you can output action='HOLD' with reasoning 'REQUEST_INFO: <question>'."
        
        # Or better: Add a dedicated field to StrategyProposal "request_info"
        # But modifying Pydantic model requires frontend changes.
        # Let's use the 'reasoning' hack for MVP.
        
        prompt_instruction = ""
        if not state.analyst_feedback: # Only ask once to avoid infinite loop
             prompt_instruction = "\n\n[LOOP INSTRUCTION] If the Analyst Report is ambiguous or missing key data (e.g. specific timeframe divergence), you may request clarification. To do this, set action='HOLD' and start your reasoning with 'REQUEST_INFO: <your question>'."

        try:
            result = await self.call_llm(
                prompt_vars={
                    "user_strategy": user_strategy_config + prompt_instruction,
                    "market_data": market_summary,
                    "analyst_report": f"Analyst Bias: {report.trading_bias} (Confidence: {report.confidence if hasattr(report, 'confidence') else 0.5})",
                    "account_balance": f"{state.account_balance:.2f}",
                    "memory_context": memory_context + "\n\n" + risk_calc_context,
                    "current_positions": positions_str,
                    "review_feedback": review_feedback,
                    "regime_context": regime_context,
                    "microstructure_context": microstructure_context,
                    "portfolio_context": portfolio_context,
                    "execution_constraints": execution_constraints
                },
                output_model=StrategyProposal
            )
            
            proposal = StrategyProposal(**result)
            preferred_order_type = "MARKET"
            if state.execution_constraints:
                preferred_order_type = str(state.execution_constraints.get("preferred_order_type", "MARKET") or "MARKET")
            if proposal.action in ["LONG", "SHORT", "BUY"] and not proposal.order_type:
                proposal.order_type = preferred_order_type
            if proposal.action in ["LONG", "SHORT", "BUY"] and not proposal.trigger_condition and preferred_order_type == "LIMIT":
                proposal.trigger_condition = "等待盘口流动性恢复后挂限价单执行"
            
            # Check for REQUEST_INFO in reasoning
            if "REQUEST_INFO:" in proposal.reasoning and not state.analyst_feedback:
                 question = proposal.reasoning.split("REQUEST_INFO:")[1].split("||")[0].strip()
                 await self.think(f"Requesting more info from Analyst: {question}", session_id)
                 return {"analyst_feedback": question}

            # Handle default CLOSE quantity (If Action is SELL/CLOSE/COVER but Qty is None/0, assume FULL CLOSE)
            # This logic is a safety net if LLM fails to follow the "CRITICAL" instruction
            if proposal.action in ["SELL", "CLOSE", "COVER"] and (not proposal.quantity or proposal.quantity == 0):
                # Fetch current position size
                if state.positions:
                    my_pos = [p for p in state.positions if p['symbol'] == symbol]
                    if my_pos:
                        # Assuming single position per symbol for now, or sum them up
                        # Backend logic uses FIFO, so total size is what matters
                        total_size = sum(float(p['size'] if 'size' in p else p['quantity']) for p in my_pos)
                        if total_size > 0:
                            proposal.quantity = total_size
                            await self.think(f"Auto-adjusted Quantity to Full Position: {total_size}", session_id)

            if proposal.action in ["LONG", "SHORT", "BUY"]:
                missing_critical = []
                if proposal.entry_price is None: missing_critical.append("entry_price")
                if proposal.stop_loss is None: missing_critical.append("stop_loss")
                if proposal.take_profit is None: missing_critical.append("take_profit")
                
                if missing_critical:
                    await self.think(
                        f"CRITICAL SCHEMA ERROR: opening action missing {', '.join(missing_critical)}. Blocking proposal and forcing HOLD.",
                        session_id,
                        log_type="error"
                    )
                    proposal.action = "HOLD"
                    proposal.order_type = "MARKET"
                    proposal.trigger_condition = None
                    proposal.entry_price = None
                    proposal.quantity = None
                    proposal.stop_loss = None
                    proposal.take_profit = None
                    proposal.confidence = min(float(proposal.confidence or 0.0), 0.2)
                    proposal.reasoning = f"BLOCKED_MISSING_FIELDS: {', '.join(missing_critical)}"
                    proposal.assumptions.append("MISSING_CRITICAL_FIELDS_BLOCK")

            if proposal.action == "HOLD":
                reasoning_text = proposal.reasoning.replace(" || ", "\n")
                prefix = f"[Rev. {state.strategy_revision_round}] " if state.strategy_revision_round > 0 else ""
                await self.say(
                    f"{prefix}DECISION: HOLD\nSTATUS: Bias {report.trading_bias} | Confidence {proposal.confidence:.2f} | Risk {report.key_risk}\n{reasoning_text}",
                    session_id,
                    artifact={
                        "action": "HOLD",
                        "confidence": proposal.confidence,
                        "bias": report.trading_bias,
                        "risk": report.key_risk,
                        "reasoning": proposal.reasoning,
                        "assumptions": proposal.assumptions,
                        "revision": state.strategy_revision_round,
                        "account_balance": state.account_balance,
                        "current_positions": positions_str,
                        "market_price": state.market_data.price
                    }
                )
            else:
                entry_val = proposal.entry_price if proposal.entry_price is not None else state.market_data.price
                entry_str = f"{entry_val:.2f}" + (" (Mkt)" if proposal.entry_price is None else "")
                
                qty_str = f"{proposal.quantity:.4f}" if proposal.quantity is not None else "N/A"
                sl_str = f"{proposal.stop_loss:.2f}" if proposal.stop_loss is not None else "N/A"
                tp_str = f"{proposal.take_profit:.2f}" if proposal.take_profit is not None else "N/A"
                conf_str = f"{proposal.confidence:.2f}" if proposal.confidence is not None else "N/A"
                
                rr = "N/A"
                if proposal.entry_price and proposal.stop_loss and proposal.take_profit:
                    risk = abs(proposal.entry_price - proposal.stop_loss)
                    reward = abs(proposal.take_profit - proposal.entry_price)
                    if risk > 0:
                        rr = f"{reward / risk:.2f}"
                metrics = compute_trade_metrics(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit)
                reasoning_text = proposal.reasoning.replace(" || ", "\n")
                prefix = f"[Rev. {state.strategy_revision_round}] " if state.strategy_revision_round > 0 else ""
                await self.say(
                    f"{prefix}DECISION: {proposal.action}\nPLAN: Entry {entry_str} | SL {sl_str} | TP {tp_str} | Qty {qty_str} | R/R {rr} | Confidence {conf_str}\n{reasoning_text}",
                    session_id,
                    artifact={
                        "action": proposal.action,
                        "entry": proposal.entry_price,
                        "sl": proposal.stop_loss,
                        "tp": proposal.take_profit,
                        "quantity": proposal.quantity,
                        "rr": rr,
                        "confidence": proposal.confidence,
                        "reasoning": proposal.reasoning,
                        "self_check": proposal.self_check, # Add self_check to artifact
                        "assumptions": proposal.assumptions,
                        "sl_distance_pct": metrics.get("sl_distance_pct"),
                        "direction_ok": metrics.get("direction_ok"),
                        "revision": state.strategy_revision_round,
                        "account_balance": state.account_balance,
                        "current_positions": positions_str,
                        "market_price": state.market_data.price
                    }
                )
                
            return {"bear_proposal": proposal}
            
        except Exception as e:
            await self.think(f"Strategy generation failed: {str(e)}", session_id)
            return {}
