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
                    "review_feedback": review_feedback_str
                },
                output_model=StrategyProposal
            )

            proposal = self._normalize_proposal(result)
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
            await self.think(f"Arbitration Complete. Chosen Action: {proposal.action}", session_id)
            return {"strategy_proposal": proposal}

        except Exception as e:
            await self.think(f"Failed to arbitrate: {e}", session_id)
            return {}
