from dataclasses import dataclass
from typing import Any, Dict

from model.state import AgentState, MarketData
from services.market_data import market_data_service
from services.market_intel import market_intel_service
from services.safety_guard import safety_guard_service
from services.system_config import system_config_service
from model.policies import DataRoutingPolicy, OrchestrationConfig


@dataclass
class WorkflowStateBuildResult:
    state: AgentState
    safety: Dict[str, Any]
    artifact: Dict[str, Any]


class WorkflowStateBuilder:
    def _load_data_routing_policy(self) -> Dict[str, Any]:
        raw = system_config_service.get_json("DATA_ROUTING_POLICY")
        if isinstance(raw, dict):
            return DataRoutingPolicy(**raw).model_dump()
        return DataRoutingPolicy().model_dump()

    def _load_orchestration_config(self) -> Dict[str, Any]:
        raw = system_config_service.get_json("WORKFLOW_ORCHESTRATION_CONFIG")
        if isinstance(raw, dict):
            return OrchestrationConfig(**raw).model_dump()
        return OrchestrationConfig().model_dump()

    async def build(
        self,
        symbol: str,
        session_id: str,
        account_balance: float,
        positions: list,
    ) -> WorkflowStateBuildResult:
        market_snapshot = market_data_service.get_full_snapshot(symbol)
        desired_notional = max(100.0, account_balance * 0.01)
        unresolved_todos = []
        data_quality = "ok"
        ticker_depth = await market_intel_service.fetch_ticker_depth(symbol=symbol, levels=10)
        kline_1m = await market_intel_service.fetch_klines(symbol=symbol, interval="1m", limit=180)

        if float(market_snapshot.get("price", 0.0) or 0.0) <= 0.0:
            ticker_price = float(ticker_depth.get("price", 0.0) or 0.0)
            kline_price = 0.0
            if kline_1m:
                try:
                    kline_price = float(kline_1m[-1].get("close", 0.0) or 0.0)
                except Exception:
                    kline_price = 0.0
            fallback_price = ticker_price if ticker_price > 0 else kline_price
            if fallback_price > 0:
                print(f"Warning: price snapshot unavailable for {symbol}, fallback to live market price {fallback_price}", flush=True)
                market_snapshot["price"] = fallback_price
                data_quality = "degraded_price_fallback"
            else:
                unresolved_todos.append(f"{symbol} 缺少可用价格快照，已退化为风控模式")
                market_snapshot["price"] = 0.0
                data_quality = "blocked_no_price"

        market_data = MarketData(
            symbol=symbol,
            timeframe="1m",
            price=market_snapshot["price"],
            volume=market_snapshot["volume"],
            indicators=market_snapshot["indicators"],
        )

        if not kline_1m:
            unresolved_todos.append(f"{symbol} 缺少可用的 1m K线数据，使用基础模式运行")
            if data_quality == "ok":
                data_quality = "degraded_no_kline"
        microstructure = market_intel_service.build_microstructure_snapshot(ticker_depth, desired_notional)
        regime = market_intel_service.classify_regime(kline_1m)
        portfolio_context = market_intel_service.build_portfolio_context(
            account_balance=account_balance,
            positions=positions,
            mark_price=market_data.price,
        )
        execution_constraints = market_intel_service.build_execution_constraints(regime=regime, micro=microstructure)
        routing_policy = self._load_data_routing_policy()
        orchestration_config = self._load_orchestration_config()
        execution_constraints["data_routing_policy"] = routing_policy
        execution_constraints["max_revision_rounds"] = int(orchestration_config.get("max_revision_rounds", 2))
        execution_constraints["data_quality"] = data_quality
        execution_constraints["data_quality_reasons"] = list(unresolved_todos)
        safety = safety_guard_service.evaluate(
            market_data={"price": market_data.price},
            micro=microstructure,
            portfolio=portfolio_context,
        )
        if safety.get("reason") == "portfolio_leverage_too_high":
            execution_constraints["deleveraging_required"] = True
            execution_constraints["reduce_only"] = True
            execution_constraints["deleveraging_reason"] = "portfolio_leverage_too_high"
            execution_constraints["current_implied_leverage"] = float(portfolio_context.get("implied_leverage", 0.0) or 0.0)
            execution_constraints["target_max_leverage"] = 4.0
            unresolved_todos.append("进入去杠杆模式: 禁止新增风险敞口，优先减仓")
        if not safety.get("allowed", True):
            unresolved_todos.append(f"触发保护机制: {safety.get('reason')}")

        state = AgentState(
            session_id=session_id,
            market_data=market_data,
            account_balance=account_balance,
            positions=positions,
            market_regime=regime,
            microstructure=microstructure,
            portfolio_context=portfolio_context,
            execution_constraints=execution_constraints,
            unresolved_todos=unresolved_todos,
        )

        artifact = {
            "market_snapshot": market_data.model_dump(),
            "balance": account_balance,
            "positions": positions,
            "market_regime": regime,
            "microstructure": microstructure,
            "portfolio_context": portfolio_context,
            "execution_constraints": execution_constraints,
            "safety_guard": safety,
            "unresolved_todos": unresolved_todos,
        }

        return WorkflowStateBuildResult(state=state, safety=safety, artifact=artifact)


workflow_state_builder = WorkflowStateBuilder()
