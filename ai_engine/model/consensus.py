"""
Consensus Engine — pre-arbitration rule layer.

Detects agreement / disagreement patterns across the Strategy Masters'
debate thread and produces a structured `ConsensusReport` that the
Finalizer receives as a strong prior. This is "system 1" thinking that
runs before the Finalizer's LLM-based "system 2" reasoning.

The goal is to convert the messy N-persona debate into actionable
structural signals:
  - hold_bias: should the PM default to HOLD?
  - dominant_action: which action has the strongest structural support?
  - conflict_grade: how severe is the disagreement (0=aligned, 3=war)
  - cited_turn_ids: the strongest turns to reference in the reasoning

This module is PURE — no LLM, no DB, no async. It is a deterministic
function over `state.debate_thread`.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from model.state import DebateTurn


# Actions grouped by directional bias. Used to detect "opposite actions".
BULLISH_ACTIONS = {"BUY", "LONG"}
BEARISH_ACTIONS = {"SELL", "SHORT", "COVER"}
NEUTRAL_ACTIONS = {"HOLD"}


def _action_bias(action: str) -> str:
    """Map an action to its directional bias: 'bull', 'bear', or 'neutral'."""
    a = (action or "").upper()
    if a in BULLISH_ACTIONS:
        return "bull"
    if a in BEARISH_ACTIONS:
        return "bear"
    return "neutral"


class ConsensusReport(BaseModel):
    """
    Structured snapshot of the debate's structural agreement. The Finalizer
    receives this as part of its preamble so it can reason about *what the
    room looks like*, not just *what each person said*.
    """

    n_personas: int = Field(description="Distinct strategy masters that participated")
    n_rounds: int = Field(description="Number of debate rounds observed (typically 1-3)")
    conflict_grade: int = Field(
        description="0=aligned, 1=soft divergence, 2=strong divergence, 3=conviction war"
    )
    hold_bias: bool = Field(
        description="True if the engine recommends defaulting to HOLD (e.g. on conviction war or all-noise)"
    )
    dominant_action: Optional[str] = Field(
        default=None,
        description="The action with the strongest structural support (after weighting); None if no clear winner",
    )
    dominant_action_weight: float = Field(
        default=0.0,
        description="Sum of confidence-weighted votes for the dominant action (0.0-1.0+)"
    )
    converging_personas: List[str] = Field(
        default_factory=list,
        description="Persona IDs that CHANGED their action between rounds (treated as 'informed by rebuttal')"
    )
    softening_personas: List[str] = Field(
        default_factory=list,
        description="Persona IDs whose confidence DECREASED across rounds (treated as 'weakening')"
    )
    bullish_strength: float = Field(default=0.0, description="Aggregate confidence-weighted strength of bull case")
    bearish_strength: float = Field(default=0.0, description="Aggregate confidence-weighted strength of bear case")
    strongest_turns: List[str] = Field(
        default_factory=list,
        description="Top-N turn_ids the Finalizer should cite in its reasoning (e.g. R2_buffett)"
    )
    rule_triggers: List[str] = Field(
        default_factory=list,
        description="Human-readable list of which consensus rules fired (for audit + Finalizer context)"
    )


def _latest_turn_per_persona(turns: List[DebateTurn]) -> Dict[str, DebateTurn]:
    """Return the latest turn of each persona (highest round number)."""
    latest: Dict[str, DebateTurn] = {}
    for t in turns:
        existing = latest.get(t.agent_id)
        if existing is None or t.round > existing.round:
            latest[t.agent_id] = t
    return latest


def _first_turn_per_persona(turns: List[DebateTurn]) -> Dict[str, DebateTurn]:
    """Return the first (R1) turn of each persona."""
    first: Dict[str, DebateTurn] = {}
    for t in turns:
        if t.agent_id not in first or t.round < first[t.agent_id].round:
            first[t.agent_id] = t
    return first


def detect_consensus(turns: List[DebateTurn]) -> ConsensusReport:
    """
    Run the consensus rules over a debate thread and return a structured report.

    The rules are intentionally simple and explainable — this is "system 1"
    reasoning that runs BEFORE the LLM-based "system 2" arbitration.
    """
    if not turns:
        return ConsensusReport(
            n_personas=0,
            n_rounds=0,
            conflict_grade=0,
            hold_bias=True,  # no debate → no edge → HOLD
            rule_triggers=["no_debate_hold"],
        )

    personas = sorted({t.agent_id for t in turns})
    rounds = sorted({t.round for t in turns})
    latest = _latest_turn_per_persona(turns)
    first = _first_turn_per_persona(turns)

    # ── Aggregate strength by directional bias (using LATEST round) ──
    bullish_strength = 0.0
    bearish_strength = 0.0
    for pid, turn in latest.items():
        if _action_bias(turn.action) == "bull":
            bullish_strength += turn.confidence
        elif _action_bias(turn.action) == "bear":
            bearish_strength += turn.confidence

    # ── Convergence: did anyone CHANGE action across rounds? ──
    converging: List[str] = []
    softening: List[str] = []
    for pid in personas:
        r1 = first.get(pid)
        r_last = latest.get(pid)
        if r1 and r_last and r1.round != r_last.round:
            if r1.action != r_last.action:
                converging.append(pid)
            if r_last.confidence < r1.confidence - 0.1:
                softening.append(pid)

    # ── Per-action weighted vote (latest round) ──
    action_weight: Dict[str, float] = {}
    for pid, turn in latest.items():
        action_weight[turn.action] = action_weight.get(turn.action, 0.0) + turn.confidence

    # ── Conflict grade ──
    rule_triggers: List[str] = []
    conflicting_conviction = (
        bullish_strength > 0.7
        and bearish_strength > 0.7
        and len(latest) >= 2
    )
    if conflicting_conviction:
        conflict_grade = 3
        rule_triggers.append("conflicting_high_conviction")
    elif bullish_strength > 0.5 and bearish_strength > 0.5:
        conflict_grade = 2
        rule_triggers.append("dual_side_pressure")
    elif abs(bullish_strength - bearish_strength) < 0.2 and (bullish_strength + bearish_strength) > 0.4:
        conflict_grade = 1
        rule_triggers.append("soft_divergence")
    else:
        conflict_grade = 0
        rule_triggers.append("aligned_or_one_sided")

    # ── Dominant action ──
    if action_weight:
        dominant_action, dominant_weight = max(action_weight.items(), key=lambda x: x[1])
    else:
        dominant_action, dominant_weight = None, 0.0

    # ── HOLD bias decision ──
    hold_bias = False
    max_conf = max((t.confidence for t in latest.values()), default=0.0)

    if conflict_grade == 3:
        # Rule 3: conviction war
        hold_bias = True
        rule_triggers.append("rule3_conflicting_conviction_hold")
    elif max_conf < 0.5:
        # Rule 5: pure noise
        hold_bias = True
        rule_triggers.append("rule5_pure_noise_hold")
    elif len(latest) == 1 and NEUTRAL_ACTIONS.intersection({latest[personas[0]].action}):
        # Single persona says HOLD and that's the only signal
        hold_bias = True
        rule_triggers.append("single_hold_passthrough")
    # Rule 1 (unanimity) and Rule 4 (soft dominance) are NOT hold biases;
    # they are handled by the Finalizer's own reasoning with this report as context.

    # ── Strongest turns to cite (for reasoning disclosure) ──
    # Pick the latest turn of each persona that materially shaped the debate:
    # - the highest-confidence bull persona
    # - the highest-confidence bear persona
    # - any converging/softening persona (interesting narrative)
    cite_set: Dict[str, DebateTurn] = {}
    bull_pids = [pid for pid, t in latest.items() if _action_bias(t.action) == "bull"]
    bear_pids = [pid for pid, t in latest.items() if _action_bias(t.action) == "bear"]
    if bull_pids:
        top = max(bull_pids, key=lambda p: latest[p].confidence)
        cite_set[top] = latest[top]
    if bear_pids:
        top = max(bear_pids, key=lambda p: latest[p].confidence)
        cite_set[top] = latest[top]
    for pid in converging + softening:
        if pid in latest:
            cite_set[pid] = latest[pid]
    # Always include the most recent turn for context
    most_recent = max(turns, key=lambda t: t.round)
    cite_set[most_recent.agent_id] = most_recent

    strongest_turns = sorted(
        (f"R{t.round}_{t.agent_id}" for t in cite_set.values()),
        key=lambda s: (-int(s.split("_")[0].lstrip("R")), s),
    )

    return ConsensusReport(
        n_personas=len(personas),
        n_rounds=len(rounds),
        conflict_grade=conflict_grade,
        hold_bias=hold_bias,
        dominant_action=dominant_action,
        dominant_action_weight=round(dominant_weight, 3),
        converging_personas=converging,
        softening_personas=softening,
        bullish_strength=round(bullish_strength, 3),
        bearish_strength=round(bearish_strength, 3),
        strongest_turns=strongest_turns,
        rule_triggers=rule_triggers,
    )


def format_consensus_for_prompt(report: ConsensusReport) -> str:
    """
    Render a ConsensusReport as a structured markdown block that can be
    prepended to the Finalizer's LLM prompt. Plain language, no jargon.
    """
    lines: List[str] = []
    lines.append("# Pre-Arbitration Consensus Report (system 1)")
    lines.append("")
    lines.append(f"- **Personas**: {report.n_personas}")
    lines.append(f"- **Rounds**: {report.n_rounds}")
    lines.append(f"- **Conflict grade**: {report.conflict_grade}/3 "
                 f"({'aligned' if report.conflict_grade == 0 else 'war' if report.conflict_grade == 3 else 'divergence'})")
    lines.append(f"- **Hold bias**: {'YES (default to HOLD unless you have an explicit override)' if report.hold_bias else 'no'}")
    lines.append(f"- **Bullish strength**: {report.bullish_strength:.2f}")
    lines.append(f"- **Bearish strength**: {report.bearish_strength:.2f}")
    if report.dominant_action:
        lines.append(f"- **Dominant action (by weighted vote)**: {report.dominant_action} @ {report.dominant_action_weight:.2f}")
    if report.converging_personas:
        lines.append(f"- **Converging (changed action across rounds)**: {', '.join(report.converging_personas)}")
    if report.softening_personas:
        lines.append(f"- **Softening (confidence dropped across rounds)**: {', '.join(report.softening_personas)}")
    if report.strongest_turns:
        lines.append(f"- **Strongest turns to cite**: {', '.join(report.strongest_turns)}")
    if report.rule_triggers:
        lines.append(f"- **Rules fired**: {', '.join(report.rule_triggers)}")

    lines.append("")
    lines.append("# Your job (system 2)")
    lines.append("Apply the multi-persona consensus rules from your system prompt. If `hold_bias` is YES, "
                 "you MUST default to HOLD unless you can articulate an explicit override reason in `reasoning`. "
                 "Otherwise, use the `dominant_action` and the cited turns to draft a StrategyProposal that "
                 "explicitly references the debate turns that drove your decision.")
    return "\n".join(lines)
