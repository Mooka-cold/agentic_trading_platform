from dataclasses import dataclass
from typing import Any, Dict

from model.state import AgentState, MarketData
from services.market_data import market_data_service
from services.market_intel import market_intel_service
from services.safety_guard import safety_guard_service


@dataclass
class WorkflowStateBuildResult:
    state: AgentState
    safety: Dict[str, Any]
    artifact: Dict[str, Any]


class WorkflowStateBuilder:
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
        execution_constraints["data_quality"] = data_quality
        execution_constraints["data_quality_reasons"] = list(unresolved_todos)
        safety = safety_guard_service.evaluate(
            market_data={"price": market_data.price},
            micro=microstructure,
            portfolio=portfolio_context,
        )
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
