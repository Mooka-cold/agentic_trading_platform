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

class Reviewer(BaseAgent):
    def __init__(self):
        super().__init__("reviewer", "The Reviewer")

    def infer_asset_class(self, symbol: str) -> str:
        """Infer asset class from symbol for adaptive risk."""
        sym = symbol.upper()
        if sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]:
            return "Major Crypto"
        elif "/USDT" in sym or "/USDC" in sym:
            return "Altcoins/Meme"
        elif sym in ["SPX", "NDX", "DJI"]:
            return "Equities/Indices"
        elif "EUR" in sym or "USD" in sym or "JPY" in sym:
             if "/" in sym: # Very basic check for forex pairs like EUR/USD
                 return "Forex"
        return "Altcoins/Meme" # Default fallback (safest/tightest)

    def get_missing_proposal_fields(self, proposal: StrategyProposal) -> list[str]:
        missing = []
        if not proposal.action:
            missing.append("action")
        if not proposal.reasoning:
            missing.append("reasoning")
        if proposal.confidence is None:
            missing.append("confidence")
        
        is_opening = proposal.action and proposal.action.upper() in ["LONG", "SHORT", "BUY"]
        if is_opening:
            if proposal.entry_price is None:
                missing.append("entry_price")
            if proposal.stop_loss is None:
                missing.append("stop_loss")
            if proposal.take_profit is None:
                missing.append("take_profit")
            if proposal.quantity is None:
                missing.append("quantity")
                
        if proposal.assumptions is None:
            missing.append("assumptions")
            
        return missing

    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        proposal = state.strategy_proposal
        
        if not proposal:
            await self.think("No strategy proposal received. Skipping risk review.", session_id)
            return {}

        if proposal.action == "HOLD":
            await self.say(
                f"DECISION: SKIP REVIEW | Action: HOLD | Confidence: {proposal.confidence:.2f} | Reason: {proposal.reasoning}",
                session_id,
                artifact={
                    "action": "HOLD",
                    "verdict": "SKIPPED",
                    "reasoning": proposal.reasoning
                }
            )
            return {}
            
        await self.think(f"Validating risk parameters for {proposal.action}...", session_id)
        
        # 0. Asset Class Identification
        asset_class = self.infer_asset_class(state.market_data.symbol)
        leverage = 1.0 # Default Spot
        
        # ... (rest of logic)
        missing_fields = self.get_missing_proposal_fields(proposal)
        if missing_fields:
            # Check if it's a closing operation, they don't need SL/TP
            is_opening = proposal.action.upper() in ["LONG", "SHORT", "BUY"]
            if is_opening:
                verdict = RiskVerdict(
                    approved=False,
                    risk_score=85.0,
                    message=f"Missing required proposal fields: {', '.join(missing_fields)}",
                    reject_code="MISSING_FIELDS",
                    fix_suggestions={"required_fields": missing_fields},
                    checks={"contract": "FAIL"}
                )
                await self.say(
                    f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                    session_id,
                    artifact={
                        "verdict": "REJECTED",
                        "code": verdict.reject_code,
                        "fix_suggestions": verdict.fix_suggestions
                    }
                )
                return {
                    "risk_verdict": verdict,
                    "review_feedback": {
                        "reject_code": verdict.reject_code,
                        "message": verdict.message,
                        "fix_suggestions": verdict.fix_suggestions,
                        "checks": verdict.checks
                    }
                }

        entry_for_risk = proposal.entry_price if proposal.entry_price is not None else state.market_data.price
        atr_val = 0.0
        try:
            atr_val = float(state.market_data.indicators.get("atr", 0.0) or 0.0)
        except Exception:
            atr_val = 0.0
        if atr_val <= 0 and entry_for_risk and entry_for_risk > 0:
            atr_val = float(entry_for_risk) * 0.02
        atr_pct = (float(atr_val) / float(entry_for_risk)) if entry_for_risk and entry_for_risk > 0 else 0.02
        sl_distance_limit_pct = max(0.03, 2.0 * atr_pct)

        metrics = compute_trade_metrics(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit)
        
        # Determine which checks to apply based on Action Type
        # OPENING positions (LONG, SHORT, BUY) require strict Risk/Reward and SL checks.
        # CLOSING positions (SELL, COVER, CLOSE) are risk reduction events, so R/R checks are irrelevant.
        is_opening = proposal.action.upper() in ["LONG", "SHORT", "BUY"]
        gate_mode = "normal"
        gate_reason = None
        if state.sentiment_report:
            gate_mode = str(getattr(state.sentiment_report, "trade_gate", "normal") or "normal")
            gate_reason = getattr(state.sentiment_report, "trigger_reason", None)
        execution_constraints = state.execution_constraints or {}
        data_quality = str(execution_constraints.get("data_quality", "ok") or "ok")
        data_quality_reasons = execution_constraints.get("data_quality_reasons", [])
        if is_opening and data_quality == "blocked_no_price":
            verdict = RiskVerdict(
                approved=False,
                risk_score=95.0,
                message="Blocked by data quality guard: no reliable price snapshot.",
                reject_code="DATA_QUALITY_BLOCKED",
                fix_suggestions={"required": ["reliable_market_price"]},
                checks={"data_quality": "FAIL"}
            )
            await self.say(
                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                session_id,
                artifact={
                    "verdict": "REJECTED",
                    "code": verdict.reject_code,
                    "data_quality": data_quality,
                    "data_quality_reasons": data_quality_reasons
                }
            )
            return {
                "risk_verdict": verdict,
                "review_feedback": {
                    "reject_code": verdict.reject_code,
                    "message": verdict.message,
                    "fix_suggestions": verdict.fix_suggestions,
                    "checks": verdict.checks
                }
            }
        gate_policy = execution_constraints.get("gate_policy", {})
        review_only_policy = gate_policy.get("review_only", {"qty_mult": 0.25, "sl_widen_mult": 1.5})
        risk_reduced_policy = gate_policy.get("risk_reduced", {"qty_mult": 0.5, "sl_widen_mult": 1.25})
        rr_floor = float(execution_constraints.get("rr_floor", 1.5) or 1.5)
        if is_opening and data_quality != "ok":
            original_qty = proposal.quantity
            if proposal.quantity is not None:
                proposal.quantity = max(0.0, proposal.quantity * 0.5)
            rr_floor = max(rr_floor, 1.6)
            await self.say(
                f"DATA_QUALITY_GUARD: {data_quality} | Qty {original_qty} -> {proposal.quantity} | RR floor -> {rr_floor}",
                session_id,
                artifact={
                    "data_quality": data_quality,
                    "data_quality_reasons": data_quality_reasons,
                    "quantity_before": original_qty,
                    "quantity_after": proposal.quantity,
                    "rr_floor": rr_floor
                }
            )
        
        if is_opening:
            await self.say(
                f"TRADE_GATE: {gate_mode} | Trigger: {gate_reason or 'n/a'}",
                session_id,
                artifact={
                    "gate_mode": gate_mode,
                    "trigger_reason": gate_reason,
                    "urgent_event": bool(getattr(state.sentiment_report, "urgent_event", False)) if state.sentiment_report else False,
                    "sample_count": int(getattr(state.sentiment_report, "sample_count", 0)) if state.sentiment_report else 0,
                    "conflicts": list(getattr(state.sentiment_report, "aggregation_conflicts", [])) if state.sentiment_report else []
                }
            )

        if is_opening and gate_mode == "review_only":
            original_qty = proposal.quantity
            if proposal.quantity is not None:
                proposal.quantity = max(0.0, proposal.quantity * float(review_only_policy.get("qty_mult", 0.25)))
            
            # Check if this proposal's SL has already been widened in a previous revision
            # We can use the presence of "widened_by" in proposal.reasoning or rely on a state flag,
            # but to be stateless, we check if the current SL distance is already >= expected widened distance.
            # A simpler heuristic: only widen if RR is exactly what Strategist typically outputs initially (e.g., RR is very tight).
            # Better approach: check if distance is already quite large relative to ATR.
            
            if proposal.entry_price is not None and proposal.stop_loss is not None and proposal.take_profit is not None:
                distance = abs(proposal.entry_price - proposal.stop_loss)
                widen_mult = float(review_only_policy.get("sl_widen_mult", 1.5))
                
                # Check if SL is already wide enough (>= 1.5x ATR). If it is, assume Strategist already widened it.
                is_already_widened = distance >= (atr_val * (widen_mult - 0.1)) if atr_val > 0 else False
                
                if not is_already_widened:
                    widen = distance * (widen_mult - 1.0)
                    
                    # We also need to widen TP proportionally to maintain RR
                    original_risk = distance
                    original_reward = abs(proposal.take_profit - proposal.entry_price)
                    rr = original_reward / original_risk if original_risk > 0 else 0
                    
                    if proposal.action.upper() in ["LONG", "BUY"]:
                        proposal.stop_loss = proposal.stop_loss - widen
                    else:
                        proposal.stop_loss = proposal.stop_loss + widen

                    entry = float(proposal.entry_price)
                    capped_sl = entry * (1.0 - sl_distance_limit_pct) if proposal.action.upper() in ["LONG", "BUY"] else entry * (1.0 + sl_distance_limit_pct)
                    capped_dist_pct = abs(entry - capped_sl) / entry if entry > 0 else sl_distance_limit_pct
                    current_dist_pct = abs(entry - float(proposal.stop_loss)) / entry if entry > 0 else capped_dist_pct
                    if current_dist_pct > capped_dist_pct:
                        proposal.stop_loss = capped_sl
                        
                    # Apply the proportional widening to TP based on the final new SL distance
                    new_risk = abs(entry - float(proposal.stop_loss))
                    if rr > 0 and new_risk > 0:
                        new_reward = new_risk * rr
                        if proposal.action.upper() in ["LONG", "BUY"]:
                            proposal.take_profit = entry + new_reward
                        else:
                            proposal.take_profit = entry - new_reward

            metrics = compute_trade_metrics(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit)
            await self.say(
                f"TRADE_GATE_APPLIED: review_only (Converted to Extreme Risk Reduced) | Qty {original_qty} -> {proposal.quantity} | SL widened for volatility",
                session_id,
                artifact={
                    "gate_mode": gate_mode,
                    "quantity_before": original_qty,
                    "quantity_after": proposal.quantity,
                    "stop_loss_after": proposal.stop_loss,
                    "sl_distance_limit_pct": sl_distance_limit_pct,
                    "policy": review_only_policy
                }
            )

        if is_opening and gate_mode == "risk_reduced":
            original_qty = proposal.quantity
            if proposal.quantity is not None:
                proposal.quantity = max(0.0, proposal.quantity * float(risk_reduced_policy.get("qty_mult", 0.5)))
            
            if proposal.entry_price is not None and proposal.stop_loss is not None and proposal.take_profit is not None:
                distance = abs(proposal.entry_price - proposal.stop_loss)
                widen_mult = float(risk_reduced_policy.get("sl_widen_mult", 1.25))
                
                # Check if SL is already wide enough. If it is, assume Strategist already widened it.
                is_already_widened = distance >= (atr_val * (widen_mult - 0.1)) if atr_val > 0 else False
                
                if not is_already_widened:
                    widen = distance * (widen_mult - 1.0)
                    
                    original_risk = distance
                    original_reward = abs(proposal.take_profit - proposal.entry_price)
                    rr = original_reward / original_risk if original_risk > 0 else 0
                    
                    if proposal.action.upper() in ["LONG", "BUY"]:
                        proposal.stop_loss = proposal.stop_loss - widen
                    else:
                        proposal.stop_loss = proposal.stop_loss + widen

                    entry = float(proposal.entry_price)
                    capped_sl = entry * (1.0 - sl_distance_limit_pct) if proposal.action.upper() in ["LONG", "BUY"] else entry * (1.0 + sl_distance_limit_pct)
                    capped_dist_pct = abs(entry - capped_sl) / entry if entry > 0 else sl_distance_limit_pct
                    current_dist_pct = abs(entry - float(proposal.stop_loss)) / entry if entry > 0 else capped_dist_pct
                    if current_dist_pct > capped_dist_pct:
                        proposal.stop_loss = capped_sl
                        
                    new_risk = abs(entry - float(proposal.stop_loss))
                    if rr > 0 and new_risk > 0:
                        new_reward = new_risk * rr
                        if proposal.action.upper() in ["LONG", "BUY"]:
                            proposal.take_profit = entry + new_reward
                        else:
                            proposal.take_profit = entry - new_reward
            metrics = compute_trade_metrics(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit)
            await self.say(
                f"TRADE_GATE_APPLIED: risk_reduced | Qty {original_qty} -> {proposal.quantity} | SL widened",
                session_id,
                artifact={
                    "gate_mode": gate_mode,
                    "quantity_before": original_qty,
                    "quantity_after": proposal.quantity,
                    "stop_loss_after": proposal.stop_loss,
                    "sl_distance_limit_pct": sl_distance_limit_pct,
                    "policy": risk_reduced_policy
                }
            )
        
        # 0. Portfolio Circuit Breaker (Only for Opening New Risk)
        if is_opening:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{settings.BACKEND_URL}/api/v1/trade/risk/check")
                    if resp.status_code == 200:
                        risk_data = resp.json()
                        if not risk_data.get("allowed", True):
                            verdict = RiskVerdict(
                                approved=False,
                                risk_score=100.0,
                                message=f"Portfolio Circuit Breaker Triggered: {risk_data.get('reason')}",
                                reject_code="CIRCUIT_BREAKER",
                                fix_suggestions={"action": "Wait for daily reset or manual unlock"},
                                checks={"portfolio_limit": "FAIL"}
                            )
                            await self.say(
                                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                                session_id,
                                artifact={
                                    "verdict": "REJECTED",
                                    "code": verdict.reject_code,
                                    "reason": verdict.message
                                }
                            )
                            return {
                                "risk_verdict": verdict,
                                "review_feedback": {
                                    "reject_code": verdict.reject_code,
                                    "message": verdict.message,
                                    "fix_suggestions": verdict.fix_suggestions,
                                    "checks": verdict.checks
                                }
                            }
                            
            except Exception as e:
                print(f"[Reviewer] Portfolio check failed (proceeding): {e}")

        # 1. Check Position Existence for Closing Actions
        if not is_opening:
            symbol = state.market_data.symbol
            current_positions = [p for p in state.positions if p['symbol'] == symbol]
            
            has_position = False
            # Map action to required position side
            if proposal.action.upper() == "SELL":
                # Assuming SELL closes LONG (or is just generic close)
                has_position = any(p['side'].upper() == 'LONG' for p in current_positions)
            elif proposal.action.upper() == "COVER":
                # COVER closes SHORT
                has_position = any(p['side'].upper() == 'SHORT' for p in current_positions)
            elif proposal.action.upper() == "CLOSE":
                # Generic CLOSE - check any position
                has_position = len(current_positions) > 0
            
            if not has_position:
                 verdict = RiskVerdict(
                    approved=False,
                    risk_score=95.0,
                    message=f"No matching position found to {proposal.action} for {symbol}.",
                    reject_code="NO_OPEN_POSITION",
                    fix_suggestions={"action": "Check current positions"},
                    checks={"position_exists": "FAIL"}
                 )
                 await self.say(
                    f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                    session_id,
                    artifact={
                        "verdict": "REJECTED",
                        "code": verdict.reject_code,
                        "fix_suggestions": verdict.fix_suggestions
                    }
                 )
                 return {
                    "risk_verdict": verdict,
                    "review_feedback": {
                        "reject_code": verdict.reject_code,
                        "message": verdict.message,
                        "fix_suggestions": verdict.fix_suggestions,
                        "checks": verdict.checks
                    }
                 }
            
            # 2. Check Balance for Fees
            # If balance is negative, we might have issues paying fees, but we should probably still allow closing to prevent further loss.
            # However, user requested: "Must check account balance sufficiency for fees"
            # We assume a minimal safe threshold, e.g. > 0
            if state.account_balance <= 0:
                 verdict = RiskVerdict(
                    approved=False,
                    risk_score=99.0,
                    message=f"Insufficient balance ({state.account_balance}) to cover potential closing fees.",
                    reject_code="INSUFFICIENT_FUNDS_FEES",
                    fix_suggestions={"action": "Deposit funds"},
                    checks={"balance_fees": "FAIL"}
                 )
                 await self.say(
                    f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                    session_id,
                    artifact={
                        "verdict": "REJECTED",
                        "code": verdict.reject_code,
                        "fix_suggestions": verdict.fix_suggestions
                    }
                 )
                 return {
                    "risk_verdict": verdict,
                    "review_feedback": {
                        "reject_code": verdict.reject_code,
                        "message": verdict.message,
                        "fix_suggestions": verdict.fix_suggestions,
                        "checks": verdict.checks
                    }
                 }

        checks = {
            "sl_side": "PASS" if (not is_opening or metrics.get("sl_side_ok")) else "FAIL",
            "tp_side": "PASS" if (not is_opening or metrics.get("tp_side_ok")) else "FAIL",
            "direction": "PASS" if (not is_opening or metrics.get("direction_ok")) else "FAIL",
            "sl_distance": "PASS" if (not is_opening or (metrics.get("sl_distance_pct") is not None and metrics["sl_distance_pct"] <= sl_distance_limit_pct + 1e-4)) else "FAIL",
            "rr_ratio": "PASS" if (not is_opening or (metrics.get("rr_ratio") is not None and metrics["rr_ratio"] >= rr_floor)) else "FAIL"
        }

        review_feedback_payload = {
            "gate_mode": gate_mode,
            "gate_reason": gate_reason,
            "sl_distance_limit_pct": sl_distance_limit_pct,
            "atr": atr_val,
            "atr_pct": atr_pct,
            "rr_floor": rr_floor,
            "execution_constraints": execution_constraints,
            "computed_metrics": metrics,
            "checks": checks
        }
        
        # Override checks for Closing Actions to always PASS (unless specific logic added later)
        # User Instruction: Do NOT check RR ratio, SL/TP format, or Entry Logic for closing actions.
        if not is_opening:
            # We already handled position existence and balance above.
            # Now we explicitly force PASS on these formatting/risk metric checks.
            checks = {k: "PASS" for k in checks}

        # Instead of just creating risk verdict here, we ensure we don't return early if we want the LLM to log the interaction
        # BUT for critical failures, returning early saves LLM calls. We will keep early returns for mathematical failures.
        if checks["direction"] == "FAIL":
            verdict = RiskVerdict(
                approved=False,
                risk_score=90.0,
                message="Direction constraints failed for SL/TP relative to entry.",
                reject_code="DIRECTION_INVALID",
                fix_suggestions=build_fix_suggestions(
                    proposal.action,
                    proposal.entry_price,
                    proposal.stop_loss,
                    proposal.take_profit,
                    max_sl_distance_pct=sl_distance_limit_pct
                ),
                checks=checks
            )
            await self.say(
                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                session_id,
                artifact={
                    "verdict": "REJECTED",
                    "code": verdict.reject_code,
                    "fix_suggestions": verdict.fix_suggestions
                }
            )
            review_feedback_payload.update({
                "reject_code": verdict.reject_code,
                "message": verdict.message,
                "fix_suggestions": verdict.fix_suggestions
            })
            return {"risk_verdict": verdict, "review_feedback": review_feedback_payload}
        if checks["sl_distance"] == "FAIL":
            verdict = RiskVerdict(
                approved=False,
                risk_score=88.0,
                message=f"SL distance {((metrics.get('sl_distance_pct') or 0) * 100):.2f}% exceeds allowed {sl_distance_limit_pct * 100:.2f}%.",
                reject_code="SL_DISTANCE_EXCEED",
                fix_suggestions=build_fix_suggestions(
                    proposal.action,
                    proposal.entry_price,
                    proposal.stop_loss,
                    proposal.take_profit,
                    max_sl_distance_pct=sl_distance_limit_pct
                ),
                checks=checks
            )
            await self.say(
                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                session_id,
                artifact={
                    "verdict": "REJECTED",
                    "code": verdict.reject_code,
                    "fix_suggestions": verdict.fix_suggestions
                }
            )
            review_feedback_payload.update({
                "reject_code": verdict.reject_code,
                "message": verdict.message,
                "fix_suggestions": verdict.fix_suggestions
            })
            return {"risk_verdict": verdict, "review_feedback": review_feedback_payload}
        if checks["rr_ratio"] == "FAIL":
            verdict = RiskVerdict(
                approved=False,
                risk_score=75.0,
                message=f"R/R {metrics.get('rr_ratio'):.2f} is below {rr_floor:.2f} minimum.",
                reject_code="RR_TOO_LOW",
                fix_suggestions=build_fix_suggestions(
                    proposal.action,
                    proposal.entry_price,
                    proposal.stop_loss,
                    proposal.take_profit,
                    min_rr=rr_floor,
                    max_sl_distance_pct=sl_distance_limit_pct
                ),
                checks=checks
            )
            await self.say(
                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                session_id,
                artifact={
                    "verdict": "REJECTED",
                    "code": verdict.reject_code,
                    "fix_suggestions": verdict.fix_suggestions
                }
            )
            review_feedback_payload.update({
                "reject_code": verdict.reject_code,
                "message": verdict.message,
                "fix_suggestions": verdict.fix_suggestions
            })
            return {"risk_verdict": verdict, "review_feedback": review_feedback_payload}
        
        proposal_str = (
            f"Action: {proposal.action}, OrderType: {proposal.order_type}, Trigger: {proposal.trigger_condition}, Entry: {proposal.entry_price}, SL: {proposal.stop_loss}, "
            f"TP: {proposal.take_profit}, Qty: {proposal.quantity}, Confidence: {proposal.confidence}, "
            f"Assumptions: {proposal.assumptions}"
        )
        volatility = "Medium Volatility (ATR: 1.5%)"
        
        # Prepare Market Context for Red Team
        context_parts = []
        if state.analyst_report:
            context_parts.append(f"Analyst: {state.analyst_report.trading_bias} (Risk: {state.analyst_report.key_risk})")
        if state.sentiment_report:
            context_parts.append(f"Sentiment: Score {state.sentiment_report.score:.2f} (Drivers: {', '.join(state.sentiment_report.key_drivers)})")
        if state.macro_report:
            context_parts.append(f"Macro: {state.macro_report.regime} (Factors: {', '.join(state.macro_report.key_factors)})")
        if state.onchain_report:
            context_parts.append(f"OnChain: {state.onchain_report.signal} (Score: {state.onchain_report.score})")
            
        market_context_str = "\n".join(context_parts) if context_parts else "No market context available."
        
        try:
            # Default Risk Config (MVP)
            user_risk_config = {
                "max_position_size_usd": 10000.0,
                "risk_per_trade": "10.0%",
                "stop_loss_type": "ATR",
                "take_profit_type": "RiskReward",
                "min_risk_reward": rr_floor,
                "max_drawdown": "10.0%"
            }

            result = await self.call_llm(
                prompt_vars={
                    "user_risk_config": json.dumps(user_risk_config, indent=2),
                    "strategy_proposal": proposal_str,
                    "market_volatility": volatility,
                    "computed_metrics": json.dumps(metrics, ensure_ascii=False),
                    "account_balance": f"{state.account_balance:.2f}",
                    "market_context": market_context_str,
                    "regime_context": json.dumps(state.market_regime or {}, ensure_ascii=False),
                    "microstructure_context": json.dumps(state.microstructure or {}, ensure_ascii=False),
                    "execution_constraints": json.dumps(execution_constraints, ensure_ascii=False)
                },
                output_model=RiskVerdict
            )
            
            verdict = RiskVerdict(**result)
            if verdict.approved:
                # FORCE Python Override: If checks failed mathematically, DO NOT ALLOW LLM to approve.
                if checks.get("direction") == "FAIL" or checks.get("sl_distance") == "FAIL" or checks.get("rr_ratio") == "FAIL":
                    verdict.approved = False
                    verdict.reject_code = "POLICY_REJECT_OVERRIDE"
                    verdict.message = "System Override: LLM approved but mathematical risk checks failed."
                    verdict.checks = checks
                    if not verdict.fix_suggestions:
                        verdict.fix_suggestions = build_fix_suggestions(
                            proposal.action,
                            proposal.entry_price,
                            proposal.stop_loss,
                            proposal.take_profit,
                            min_rr=rr_floor,
                            max_sl_distance_pct=sl_distance_limit_pct
                        )
                # HARD REJECT on Low Confidence
                elif proposal.confidence < 0.70:
                    verdict.approved = False
                    verdict.reject_code = "LOW_CONFIDENCE"
                    verdict.message = f"System Override: Confidence {proposal.confidence} is below 0.70 threshold."
                    verdict.checks = checks
                    if not verdict.fix_suggestions:
                        verdict.fix_suggestions = build_fix_suggestions(
                            proposal.action,
                            proposal.entry_price,
                            proposal.stop_loss,
                            proposal.take_profit,
                            min_rr=rr_floor,
                            max_sl_distance_pct=sl_distance_limit_pct
                        )
                else:
                    verdict.reject_code = None
            else:
                if not verdict.reject_code:
                    verdict.reject_code = "POLICY_REJECT"
                if not verdict.fix_suggestions:
                    verdict.fix_suggestions = build_fix_suggestions(
                        proposal.action,
                        proposal.entry_price,
                        proposal.stop_loss,
                        proposal.take_profit,
                        min_rr=rr_floor,
                        max_sl_distance_pct=sl_distance_limit_pct
                    )
                if not verdict.checks:
                    verdict.checks = checks
            
            if verdict.approved:
                await self.say(
                    f"APPROVED {proposal.action} {state.market_data.symbol}. Risk Score: {verdict.risk_score}/100.", 
                    session_id,
                    artifact={
                        "verdict": "APPROVED",
                        "score": verdict.risk_score,
                        "checks": verdict.checks,
                        "action": proposal.action
                    },
                    symbol=state.market_data.symbol
                )
                
                # --- Execute Order ---
                await self.think("Routing order to Execution Engine...", session_id)
                try:
                    final_quantity = verdict.adjusted_size if verdict.adjusted_size is not None else proposal.quantity
                    if final_quantity is None or final_quantity <= 0:
                        verdict.approved = False
                        verdict.reject_code = "INVALID_EXECUTION_SIZE"
                        verdict.message = "Execution blocked: quantity is missing or non-positive."
                        verdict.checks = {**(verdict.checks or {}), "quantity": "FAIL"}
                        verdict.fix_suggestions = {**(verdict.fix_suggestions or {}), "required_fields": ["quantity"]}
                        await self.say(
                            f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                            session_id,
                            artifact={
                                "verdict": "REJECTED",
                                "code": verdict.reject_code,
                                "quantity": final_quantity
                            },
                            symbol=state.market_data.symbol
                        )
                        return {
                            "risk_verdict": verdict,
                            "review_feedback": {
                                "reject_code": verdict.reject_code,
                                "message": verdict.message,
                                "fix_suggestions": verdict.fix_suggestions,
                                "checks": verdict.checks
                            }
                        }
                    if verdict.adjusted_size:
                         await self.think(f"Applying Risk-Adjusted Size: {final_quantity}", session_id)

                    execution_algo = state.execution_constraints.get("execution_algo", "STANDARD") if state.execution_constraints else "STANDARD"
                    
                    data = await execution_service.execute_order(
                        action=proposal.action,
                        symbol=state.market_data.symbol,
                        quantity=final_quantity,
                        price=state.market_data.price,
                        stop_loss=proposal.stop_loss,
                        take_profit=proposal.take_profit,
                        confidence=proposal.confidence,
                        session_id=session_id,
                        order_type=proposal.order_type,
                        trigger_condition=proposal.trigger_condition,
                        execution_algo=execution_algo
                    )
                    
                    state.execution_result = data # Save result for Reflector
                    
                    if data.get("status") == "FILLED":
                        mode = data.get('mode', 'UNKNOWN')
                        pnl = data.get('pnl', 0.0)
                        pnl_str = f" | PnL: {pnl:.2f}" if pnl != 0 else ""
                        await self.say(f"EXECUTED [{mode}]: {data['status']} @ {data['executed_price']}. New Bal: {data['new_balance']}{pnl_str}", session_id)
                    else:
                        await self.think(f"Execution Failed: {data.get('message')}", session_id)
                            
                except Exception as ex:
                     await self.think(f"Execution Error: {str(ex)}", session_id)
                # ---------------------

            else:
                await self.say(
                    f"REJECTED [{verdict.reject_code}]. {verdict.message}", 
                    session_id,
                    artifact={
                        "verdict": "REJECTED",
                        "code": verdict.reject_code,
                        "reason": verdict.message[:60],
                        "fix_suggestions": verdict.fix_suggestions,
                        "checks": verdict.checks
                    }
                )
                
            if not verdict.approved:
                review_feedback_payload.update({
                    "reject_code": verdict.reject_code,
                    "message": verdict.message,
                    "fix_suggestions": verdict.fix_suggestions
                })
                return {"risk_verdict": verdict, "review_feedback": review_feedback_payload}
            return {"risk_verdict": verdict, "review_feedback": None}
            
        except Exception as e:
            await self.think(f"Risk check failed: {str(e)}", session_id)
            return {}
