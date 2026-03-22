import json
from agents.base import BaseAgent
from model.state import AgentState, StrategyProposal

class PortfolioManager(BaseAgent):
    def __init__(self):
        super().__init__("portfolio_manager", "The Portfolio Manager")

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

        try:
            result = await self.call_llm(
                prompt_vars={
                    "bull_proposal": bull.json(),
                    "bear_proposal": bear.json(),
                    "market_regime": market_regime,
                    "analyst_bias": analyst_bias,
                    "macro_context": macro_context,
                    "positions": positions_str
                },
                output_model=StrategyProposal
            )

            await self.think(f"Arbitration Complete. Chosen Action: {result.action}", session_id)
            return {"strategy_proposal": result}

        except Exception as e:
            await self.think(f"Failed to arbitrate: {e}", session_id)
            return {}
