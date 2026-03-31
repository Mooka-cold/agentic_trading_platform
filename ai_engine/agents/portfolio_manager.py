import json
from agents.base import BaseAgent
from model.state import AgentState, StrategyProposal

class PortfolioManager(BaseAgent):
    def __init__(self):
        super().__init__("portfolio_manager", "The Portfolio Manager")

    def _normalize_proposal(self, raw: StrategyProposal | dict) -> StrategyProposal:
        return raw if isinstance(raw, StrategyProposal) else StrategyProposal(**raw)

    def _to_float(self, value) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    def _apply_numeric_patch(self, proposal: StrategyProposal, field: str, target: float) -> str | None:
        if field == "entry_price":
            before = proposal.entry_price
            proposal.entry_price = target
        elif field == "stop_loss":
            before = proposal.stop_loss
            proposal.stop_loss = target
        elif field == "take_profit":
            before = proposal.take_profit
            proposal.take_profit = target
        elif field == "quantity":
            before = proposal.quantity
            proposal.quantity = max(0.0, target)
        else:
            return None
        if before is None:
            return f"{field} None -> {target:.4f}"
        if float(before) == float(target):
            return None
        return f"{field} {float(before):.4f} -> {target:.4f}"

    def _apply_review_feedback(self, proposal: StrategyProposal, feedback: dict | None) -> tuple[StrategyProposal, str | None]:
        if not feedback:
            return proposal, None
        fix_suggestions = feedback.get("fix_suggestions") or {}
        action = str(proposal.action or "").upper()
        changes: list[str] = []

        for key in ["entry_price", "stop_loss", "take_profit", "quantity"]:
            target = self._to_float(fix_suggestions.get(key))
            if target is None:
                continue
            changed = self._apply_numeric_patch(proposal, key, target)
            if changed:
                changes.append(changed)

        max_tp = self._to_float(fix_suggestions.get("max_take_profit"))
        if max_tp is not None and action in ["SHORT", "SELL", "CLOSE"] and proposal.take_profit is not None and proposal.take_profit > max_tp:
            changed = self._apply_numeric_patch(proposal, "take_profit", max_tp)
            if changed:
                changes.append(changed)

        min_tp = self._to_float(fix_suggestions.get("min_take_profit"))
        if min_tp is not None and action in ["LONG", "BUY", "COVER"] and proposal.take_profit is not None and proposal.take_profit < min_tp:
            changed = self._apply_numeric_patch(proposal, "take_profit", min_tp)
            if changed:
                changes.append(changed)

        if not changes:
            return proposal, None
        return proposal, "; ".join(changes)

    def _apply_onchain_gate_position_cap(
        self,
        proposal: StrategyProposal,
        constraints: dict,
        market_price: float,
        account_balance: float,
    ) -> tuple[StrategyProposal, str | None]:
        action = str(proposal.action or "").upper()
        if action not in ["LONG", "SHORT", "BUY"]:
            return proposal, None
        onchain_gate = str(constraints.get("onchain_trade_gate", "normal") or "normal")
        if onchain_gate not in {"risk_reduced", "review_only"}:
            return proposal, None
        gate_policy = constraints.get("gate_policy", {})
        policy = gate_policy.get(onchain_gate, {})
        qty_mult = float(policy.get("qty_mult", 0.5 if onchain_gate == "risk_reduced" else 0.25))
        hard_notional_pct = 0.006 if onchain_gate == "risk_reduced" else 0.003
        price = float(market_price or 0.0)
        balance = float(account_balance or 0.0)
        if proposal.quantity is None or proposal.quantity <= 0 or price <= 0 or balance <= 0:
            return proposal, None
        original_qty = float(proposal.quantity)
        qty_after_mult = max(0.0, original_qty * qty_mult)
        hard_qty_cap = (balance * hard_notional_pct) / price
        final_qty = max(0.0, min(qty_after_mult, hard_qty_cap))
        if final_qty >= original_qty:
            return proposal, None
        proposal.quantity = final_qty
        constraints["onchain_gate_pre_applied"] = True
        constraints["onchain_gate_pre_applied_qty_mult"] = qty_mult
        constraints["onchain_gate_hard_notional_pct"] = hard_notional_pct
        return proposal, f"onchain_gate={onchain_gate}; quantity {original_qty:.6f} -> {final_qty:.6f}; qty_mult={qty_mult:.3f}; hard_notional_pct={hard_notional_pct:.4f}"

    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        
        bull = state.bull_proposal
        bear = state.bear_proposal
        
        if not bull or not bear:
            await self.think("Missing one or both team proposals. Cannot arbitrate.", session_id)
            return {}

        await self.think("Received both Blue (Bull) and Red (Bear) proposals. Starting arbitration...", session_id)
        
        # Prepare Context
        market_regime = json.dumps(state.market_regime or {"regime": "UNKNOWN"})
        analyst_bias = state.analyst_report.trading_bias if state.analyst_report else "UNKNOWN"
        macro_context = "Neutral"
        if state.macro_report:
            macro_context = f"{state.macro_report.regime} (Risk Score: {state.macro_report.risk_score})"
            
        positions_str = json.dumps([p for p in state.positions if p['symbol'] == state.market_data.symbol]) if state.positions else "None"
        review_feedback = state.review_feedback or {}
        review_feedback_str = json.dumps(review_feedback, ensure_ascii=False)
        cross_fire_context_str = json.dumps(state.debate_notes or {}, ensure_ascii=False)

        try:
            bull_payload = bull.model_dump_json() if isinstance(bull, StrategyProposal) else json.dumps(bull, ensure_ascii=False)
            bear_payload = bear.model_dump_json() if isinstance(bear, StrategyProposal) else json.dumps(bear, ensure_ascii=False)
            result = await self.call_llm(
                prompt_vars={
                    "bull_proposal": bull_payload,
                    "bear_proposal": bear_payload,
                    "market_regime": market_regime,
                    "analyst_bias": analyst_bias,
                    "macro_context": macro_context,
                    "positions": positions_str,
                    "review_feedback": review_feedback_str,
                    "cross_fire_context": cross_fire_context_str
                },
                output_model=StrategyProposal
            )

            proposal = self._normalize_proposal(result)
            cross_fire_context = state.debate_notes or {}
            constraints = state.execution_constraints or {}
            ce_policy = constraints.get("cross_examiner_policy", {}) if isinstance(constraints, dict) else {}
            enforce_hold_bias = bool(ce_policy.get("enforce_hold_bias", False))
            if enforce_hold_bias and bool(cross_fire_context.get("hold_bias", False)):
                if str(proposal.action or "HOLD").upper() in ["LONG", "SHORT", "BUY"]:
                    original_action = proposal.action
                    proposal.action = "HOLD"
                    proposal.order_type = "MARKET"
                    proposal.trigger_condition = None
                    proposal.entry_price = None
                    proposal.quantity = None
                    proposal.stop_loss = None
                    proposal.take_profit = None
                    proposal.confidence = min(float(proposal.confidence or 0.0), 0.55)
                    proposal.reasoning = (
                        f"[PM ARBITRATION] Cross-exam hold_bias enforced. "
                        f"Original action {original_action} replaced with HOLD due to high conflict and weak score gap."
                    )
                    await self.think("Cross-exam hold_bias enforcement triggered: converted opening action to HOLD.", session_id)
            proposal, patch_desc = self._apply_review_feedback(proposal, state.review_feedback)
            if patch_desc:
                await self.think(
                    f"Applied reviewer feedback ({state.review_feedback.get('reject_code')}): {patch_desc}",
                    session_id
                )
            elif state.review_feedback:
                await self.think(
                    f"Reviewer feedback received but no auto-applicable patch: {json.dumps(state.review_feedback.get('fix_suggestions') or {}, ensure_ascii=False)}",
                    session_id
                )
            proposal, onchain_patch_desc = self._apply_onchain_gate_position_cap(
                proposal=proposal,
                constraints=constraints,
                market_price=float(state.market_data.price or 0.0),
                account_balance=float(state.account_balance or 0.0),
            )
            if onchain_patch_desc:
                await self.think(
                    f"Applied onchain gate position cap: {onchain_patch_desc}",
                    session_id
                )
            if bool(constraints.get("deleveraging_required")):
                symbol_positions = [p for p in (state.positions or []) if p.get("symbol") == state.market_data.symbol]
                long_size = sum(float(p.get("size", p.get("quantity", 0.0)) or 0.0) for p in symbol_positions if str(p.get("side", "")).upper() in ["LONG", "BUY"])
                short_size = sum(float(p.get("size", p.get("quantity", 0.0)) or 0.0) for p in symbol_positions if str(p.get("side", "")).upper() in ["SHORT", "SELL"])
                raw_action = str(proposal.action or "HOLD").upper()
                if raw_action in ["BUY", "LONG", "SHORT"]:
                    if long_size > 0:
                        reduce_qty = min(long_size, max(round(long_size * 0.15, 6), 0.001))
                        proposal.action = "SELL"
                        proposal.order_type = "MARKET"
                        proposal.trigger_condition = None
                        proposal.entry_price = None
                        proposal.quantity = reduce_qty
                        proposal.stop_loss = None
                        proposal.take_profit = None
                        proposal.confidence = min(float(proposal.confidence or 0.0), 0.45)
                        proposal.reasoning = f"DELEVERAGE_OVERRIDE: leverage too high, reduce long exposure by {reduce_qty}."
                    elif short_size > 0:
                        reduce_qty = min(short_size, max(round(short_size * 0.15, 6), 0.001))
                        proposal.action = "COVER"
                        proposal.order_type = "MARKET"
                        proposal.trigger_condition = None
                        proposal.entry_price = None
                        proposal.quantity = reduce_qty
                        proposal.stop_loss = None
                        proposal.take_profit = None
                        proposal.confidence = min(float(proposal.confidence or 0.0), 0.45)
                        proposal.reasoning = f"DELEVERAGE_OVERRIDE: leverage too high, reduce short exposure by {reduce_qty}."
                    else:
                        proposal.action = "HOLD"
                        proposal.order_type = "MARKET"
                        proposal.trigger_condition = None
                        proposal.entry_price = None
                        proposal.quantity = None
                        proposal.stop_loss = None
                        proposal.take_profit = None
                        proposal.confidence = min(float(proposal.confidence or 0.0), 0.35)
                        proposal.reasoning = "DELEVERAGE_OVERRIDE: leverage high but no matching position to reduce."
                    await self.think("Deleveraging mode active: blocked risk-increasing action and converted to risk reduction.", session_id)
            await self.think(f"Arbitration Complete. Chosen Action: {proposal.action}", session_id)
            return {"strategy_proposal": proposal, "execution_constraints": constraints}

        except Exception as e:
            await self.think(f"Failed to arbitrate: {e}", session_id)
            return {}
