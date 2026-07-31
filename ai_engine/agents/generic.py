import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Type
from model.state import AgentState, StrategyProposal, RiskVerdict, DebateTurn
from agents.base import BaseAgent


def format_news_preamble(state: AgentState) -> str:
    """
    Render state.news_digest as a compact markdown block for extra_preamble injection.

    The digest is already LLM-compressed upstream (sentiment_news_interpreter), so
    this function only does lightweight formatting — zero additional token cost.
    Noise-flagged items are annotated so agents can discount them appropriately.
    """
    digest = getattr(state, "news_digest", None) or []
    if not digest:
        return ""
    lines = ["# Latest News Context (LLM-compressed, last 24h)", ""]
    for it in digest:
        source = it.get("source") or "?"
        summary = (it.get("summary_cn") or it.get("title") or "").strip()
        assets = it.get("asset_mentions") or []
        asset_str = f" [assets: {', '.join(assets)}]" if assets else ""
        noise_str = " (noise)" if it.get("is_noise") else ""
        lines.append(f"- [{source}]{asset_str}{noise_str} {summary}")
    lines.append("")
    lines.append(
        "Use this news context to inform your analysis, but weigh it against the "
        "hard market data. Items marked (noise) are low-signal; do not let them dominate."
    )
    return "\n".join(lines)


class GenericMarketAgent(BaseAgent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, agent_id)

    async def run(self, state: AgentState) -> Dict[str, Any]:
        session_id = state.session_id
        await self.think("Analyzing market data...", session_id=session_id)

        prompt_vars = {
            "market_data": state.market_data.model_dump_json(),
            "positions": json.dumps(state.positions),
            "account_balance": state.account_balance,
        }

        # Market agents just output a generic dict of insights for now.
        # Inject LLM-compressed news context (if any) so market analysis can
        # incorporate the news dimension alongside pure price/volume data.
        news_preamble = format_news_preamble(state)
        output = await self.call_llm(
            prompt_vars,
            state=state,
            extra_preamble=news_preamble if news_preamble else None,
        )

        await self.say("Market analysis complete.", session_id=session_id, artifact={"output": output.content})

        return {"market_reports": {self.agent_id: output.content}}

class GenericDecisionAgent(BaseAgent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, agent_id)

    async def run(self, state: AgentState) -> Dict[str, Any]:
        """Legacy entry: just emit a single StrategyProposal (no debate)."""
        return await self.run_debate_round(state, round_index=1, prior_turns=[])

    async def run_debate_round(
        self,
        state: AgentState,
        round_index: int,
        prior_turns: List[DebateTurn],
    ) -> Dict[str, Any]:
        """
        Run one debate round for this persona.

        Round 1: persona forms an independent thesis based purely on the raw market data.
        Round ≥2: persona can see and rebut the theses of OTHER personas from the previous
                  round (filtered by `references` to avoid self-reference noise).
        """
        session_id = state.session_id
        await self.think(
            f"Round {round_index}: Formulating thesis...",
            session_id=session_id,
        )

        # Build a digest of prior debate for this round's prompt
        if round_index == 1 or not prior_turns:
            prior_digest = "(This is the opening round. State your independent view based purely on the raw market data. Do NOT reference other agents.)"
        else:
            other_turns = [t for t in prior_turns if t.round == round_index - 1 and t.agent_id != self.agent_id]
            if not other_turns:
                prior_digest = "(No opposing theses from previous round.)"
            else:
                lines = []
                for t in other_turns:
                    lines.append(
                        f"- [{t.agent_id}] action={t.action} conf={t.confidence:.2f}\n"
                        f"  Thesis: {t.thesis}"
                    )
                prior_digest = "\n".join(lines)

        # Debate-specific preamble: explains the debate contract and
        # suppresses the persona's normal "output StrategyProposal" requirement,
        # since in debate mode we want a DebateTurn instead.
        debate_preamble = f"""# Debate Mode (Round {round_index})

You are participating in a multi-agent investment committee. Your normal output
schema is suspended; in this mode you must return a single JSON object that
conforms to the `DebateTurn` schema. You may KEEP the persona, tone, and
philosophy defined by your system prompt, but the output contract is:

- `action`: your proposed action this round (BUY | SELL | SHORT | COVER | HOLD)
- `confidence`: 0.0~1.0, how strongly you believe in your action
- `thesis`: a 1-2 sentence core argument
- `rebuttals`: a list of targeted responses to other agents' theses (empty list in round 1)
- `references`: agent_ids you are responding to (empty list in round 1)

## Prior debate (from round {round_index - 1 if round_index > 1 else 'N/A'})
{prior_digest}

## Rules
- Stay in character: your philosophy must still color your action and confidence.
- In round 1, ignore all other agents and reason purely from the raw market data.
- In round ≥2, you MAY change your action or confidence based on other agents'
  rebuttals — but you must explicitly address the strongest counter-argument.
- Keep `thesis` under 60 words. Keep each `rebuttals` entry under 40 words.
"""

        # Append LLM-compressed news context so strategy masters can debate
        # with awareness of the news dimension (macro/regulatory/asset-specific).
        news_block = format_news_preamble(state)
        if news_block:
            debate_preamble += "\n\n" + news_block

        prompt_vars = {
            "market_reports": json.dumps(state.market_reports, ensure_ascii=False),
            "market_data": state.market_data.model_dump_json(),
            "positions": json.dumps(state.positions),
            "account_balance": state.account_balance,
            "execution_constraints": json.dumps(state.execution_constraints),
        }

        # The LLM now outputs a DebateTurn (with action, confidence, thesis, rebuttals)
        # rather than a full StrategyProposal. Finalizer will translate the winning
        # turn into a StrategyProposal in the arbitration stage.
        output = await self.call_llm(
            prompt_vars,
            state=state,
            output_model=DebateTurn,
            extra_preamble=debate_preamble,
        )

        # Fill metadata
        output.round = round_index
        output.agent_id = self.agent_id
        output.agent_name = self.name
        output.timestamp = datetime.now(timezone.utc).isoformat()
        if round_index == 1:
            output.references = []
        else:
            # Tag which other agents this turn is responding to
            output.references = sorted({t.agent_id for t in prior_turns if t.round == round_index - 1 and t.agent_id != self.agent_id})

        # Surface a human-readable line into the chat feed
        if round_index == 1:
            await self.say(
                f"Thesis: {output.thesis}",
                session_id=session_id,
                artifact=output.model_dump(),
            )
        else:
            rebuttal_summary = "; ".join(output.rebuttals) if output.rebuttals else "(no rebuttals)"
            await self.say(
                f"Updated action={output.action} conf={output.confidence:.0%} | Rebuttals: {rebuttal_summary}",
                session_id=session_id,
                artifact=output.model_dump(),
            )

        # Persist the FULL DebateTurn (round, agent_id, thesis, rebuttals, references,
        # confidence, action, timestamp) as a structured log entry so the entire debate
        # can be replayed / audited from agent_logs.artifact later, even if SSE was missed.
        await self.emit_log(
            content=f"DEBATE_TURN_R{round_index}_{self.agent_id}",
            log_type="debate",
            session_id=session_id,
            artifact=output.model_dump(),
        )

        return {"debate_turn": output}

class GenericArbitratorAgent(BaseAgent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, agent_id)

    async def run(self, state: AgentState) -> Dict[str, Any]:
        session_id = state.session_id
        await self.think("Reading the full debate thread and arbitrating...", session_id=session_id)

        # Build a chronological digest of the entire debate so the finalizer
        # can read not just votes but the actual exchange of ideas.
        debate_lines = []
        for t in state.debate_thread:
            tag = f"R{t.round} [{t.agent_id} {t.action} @ {t.confidence:.0%}]"
            line = f"{tag}: {t.thesis}"
            if t.rebuttals:
                line += "\n  Rebuttals: " + " | ".join(t.rebuttals)
            debate_lines.append(line)
        debate_digest = "\n".join(debate_lines) if debate_lines else "(No debate happened — synthesize a proposal directly from market data.)"

        # ── Run the consensus engine (system 1) BEFORE the LLM call ──
        # This converts the messy N-persona debate into structured signals
        # (hold_bias, dominant_action, conflict_grade, etc.) that the LLM
        # can reason about, instead of free-form pattern matching.
        try:
            from model.consensus import detect_consensus, format_consensus_for_prompt
            consensus = detect_consensus(state.debate_thread)
            consensus_block = format_consensus_for_prompt(consensus)
            # Persist the consensus report so the audit trail captures it.
            await self.emit_log(
                content=f"CONSENSUS_BY_{self.agent_id}",
                log_type="consensus",
                session_id=session_id,
                artifact=consensus.model_dump(),
            )
        except Exception as e:
            consensus_block = f"(Consensus engine unavailable: {e})"

        proposals_json = {k: v.model_dump() for k, v in state.decision_proposals.items()}
        prompt_vars = {
            "decision_proposals": json.dumps(proposals_json, ensure_ascii=False),
            "market_data": state.market_data.model_dump_json(),
            "positions": json.dumps(state.positions),
            "account_balance": state.account_balance,
        }

        # Inject the debate digest + consensus report as a preamble. The
        # persona's normal prompt still defines tone and philosophy; we just
        # add structured decision inputs without having to mutate the persona YAMLs.
        debate_preamble = f"""# Debate Thread (chronological)

The committee has finished a multi-round debate. Read EVERY turn before making
your final call. Pay special attention to (a) where strong rebuttals weakened
a position, and (b) whether a high-confidence stance survived rebuttals.

{debate_digest}

# ────────────────────────────────────────────────────────
{consensus_block}
# ────────────────────────────────────────────────────────

# Output Reminder
You must return a single JSON object that matches the `StrategyProposal` schema
that your persona prompt specifies. In `reasoning`, you MUST cite specific debate
turns (e.g. R2_buffett) that drove your decision. If you adopt HOLD due to
conflicting conviction, cite BOTH sides' strongest turn.
"""

        output = await self.call_llm(
            prompt_vars,
            state=state,
            output_model=StrategyProposal,
            extra_preamble=debate_preamble,
        )

        await self.say(f"Final Arbitrated Action: {output.action}", session_id=session_id, artifact=output.model_dump())

        # Persist a structured "finalize" log so the audit trail captures which
        # debate turns drove the final decision. Frontend / dashboards can later
        # diff "what each persona said" against "what the finalizer actually picked".
        await self.emit_log(
            content=f"FINALIZE_BY_{self.agent_id}",
            log_type="finalize",
            session_id=session_id,
            artifact={
                "final_action": output.action,
                "final_confidence": output.confidence,
                "reasoning": output.reasoning,
                "debate_turn_ids": [f"R{t.round}_{t.agent_id}" for t in state.debate_thread],
                "consensus": consensus.model_dump() if 'consensus' in dir() else None,
            },
        )

        return {"strategy_proposal": output}

class GenericRiskAgent(BaseAgent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, agent_id)

    async def run(self, state: AgentState) -> Dict[str, Any]:
        session_id = state.session_id
        await self.think("Evaluating risk...", session_id=session_id)
        
        prompt_vars = {
            "strategy_proposal": state.strategy_proposal.model_dump_json() if state.strategy_proposal else "{}",
            "market_data": state.market_data.model_dump_json(),
            "positions": json.dumps(state.positions),
            "account_balance": state.account_balance,
        }
        
        output = await self.call_llm(prompt_vars, state=state, output_model=RiskVerdict)
        
        verdict_str = "APPROVED" if output.approved else "REJECTED"
        await self.say(f"Risk Verdict: {verdict_str}", session_id=session_id, artifact=output.model_dump())
        
        return {"risk_verdict": output}
