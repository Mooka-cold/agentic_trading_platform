import asyncio
import httpx
from typing import Dict, Any
from model.state import AgentState, MarketData, StrategyProposal, RiskVerdict
from agents import Analyst, Strategist, Reviewer, Reflector, SentimentAgent
import redis.asyncio as redis
import json
import os
import uuid

from core.config import settings

from services.market_data import market_data_service
from services.market_intel import market_intel_service
from services.safety_guard import safety_guard_service
from services.risk_checks import get_missing_proposal_fields

from langgraph_workflow import create_trading_workflow

# Workflow Engine (Orchestrator)

class WorkflowEngine:
    def __init__(self):
        # Retry Logic for Redis Connection
        # This prevents startup crashes if Redis container is slower to start
        import time
        for attempt in range(5):
            try:
                self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                # Ping check
                # Note: async redis client is lazy, but we can't await in __init__.
                # So we assume it's okay or handle connection error later.
                break
            except Exception as e:
                print(f"Warning: Redis connection failed (Attempt {attempt+1}/5): {e}")
                time.sleep(2)
        
        self.backend_url = settings.BACKEND_URL
        
        # Continuous Mode State
        self.is_running = False
        self.stop_signal = False
        self.current_task = None
        self.latest_config = {}
        self.processing_lock = asyncio.Lock()
        
        self.reload_agents()
        # Initialize LangGraph Workflow
        self.graph_app = create_trading_workflow()

    def reload_agents(self):
        print("🔄 Reloading Agents with latest config...")
        from agents import Analyst, Reviewer, Reflector, SentimentAgent
        from agents.bull_strategist import BullStrategist
        from agents.bear_strategist import BearStrategist
        from agents.portfolio_manager import PortfolioManager
        
        self.analyst = Analyst()
        self.sentiment_agent = SentimentAgent()
        self.bull_strategist = BullStrategist()
        self.bear_strategist = BearStrategist()
        self.portfolio_manager = PortfolioManager()
        self.reviewer = Reviewer()
        self.reflector = Reflector(self.redis_client) # Pass redis_client here
        print("✅ Agents reloaded.")

    async def _fetch_account_balance_with_retry(self, retries: int = 3, retry_delay: float = 1.0) -> float:
        last_error = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(f"{self.backend_url}/api/v1/trade/paper/account")
                if res.status_code != 200:
                    raise RuntimeError(f"paper account api status={res.status_code}, body={res.text[:200]}")
                payload = res.json() if isinstance(res.json(), dict) else {}
                if "balance" not in payload:
                    raise RuntimeError("paper account api missing balance field")
                return float(payload["balance"])
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
        raise RuntimeError(f"failed to fetch account balance after {retries} attempts: {last_error}")

    async def start_loop(self, symbol: str, session_id: str):
        """
        Start continuous workflow loop. If already running, update config.
        """
        self.latest_config = {"symbol": symbol, "session_id": session_id}
        
        # Persist desired state
        await self.redis_client.set("system_status:loop_active", "true")
        await self.redis_client.set("system_status:loop_config", json.dumps(self.latest_config))
        
        if self.current_task and self.current_task.done():
            self.is_running = False
            self.current_task = None

        if self.is_running:
            print(f"[Workflow] Loop already running. Config updated for next cycle.")
            return

        self.is_running = True
        self.stop_signal = False
        self.current_task = asyncio.create_task(self._loop())
        print(f"[Workflow] Continuous Loop Started for {session_id}")

    async def stop_loop(self):
        """
        Stop the continuous loop.
        """
        # Remove persisted state
        await self.redis_client.delete("system_status:loop_active")
        
        if not self.is_running:
            return
            
        print(f"[Workflow] Stopping loop...")
        self.stop_signal = True
        if self.current_task:
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
        self.is_running = False
        print(f"[Workflow] Loop Stopped.")

    async def _loop(self):
        """
        The main infinite loop.
        """
        parent_session_id = self.latest_config.get("session_id") # Keep track of who started this
        
        while not self.stop_signal:
            try:
                symbol = self.latest_config.get("symbol")
                # Generate a NEW unique session ID for each cycle
                # Format: auto-loop-{timestamp}
                import time
                current_session_id = f"auto-{symbol}-{int(time.time())}"
                
                print(f"[Workflow] Starting Cycle for {symbol} (Session: {current_session_id})...")
                
                # Notify frontend via SSE about the new session ID? 
                # Currently frontend listens to a specific ID. 
                # This breaks the frontend "Live View" if frontend expects logs on 'parent_session_id'.
                
                # DILEMMA: 
                # 1. If we change ID, frontend stops receiving logs (unless it listens to a wildcard or we push to parent channel).
                # 2. If we keep ID, history gets polluted.
                
                # SOLUTION for MVP:
                # We use the NEW ID for database storage (so History is clean).
                # But we emit logs to Redis/SSE using BOTH IDs? 
                # Or we update `run_workflow` to accept `log_stream_id` separate from `db_session_id`.
                
                # Let's modify run_workflow signature slightly to support this decoupling if needed.
                # For now, let's assume `session_id` is used for both DB and Logging.
                # If we change it here, the Frontend (listening to `parent_session_id`) will see nothing.
                
                # QUICK FIX:
                # Use the SAME ID for the loop (so Frontend works), BUT add a "Cycle Index" to the log?
                # No, that doesn't solve the "History Page" pollution.
                
                # BETTER FIX:
                # Frontend should listen to "active_session" updates.
                # But simplest for now: 
                # Let's keep using the session_id passed from frontend for the FIRST run.
                # For subsequent runs, we generate new IDs?
                # If we do that, the user has to refresh the page to see new logs.
                
                # COMPROMISE:
                # 1. Use `current_session_id` for DB and Agent execution.
                # 2. But explicitly tell Agents to broadcast logs to `parent_session_id` channel TOO?
                # That requires deep changes in Agent class.
                
                # ALTERNATIVE:
                # Frontend "AgentThinkingCard" is a "Live Monitor". It should subscribe to "monitor:{symbol}" channel, not a specific session ID.
                # But current architecture subscribes to `/stream/logs/{session_id}`.
                
                # Let's stick to generating NEW IDs for DB sanity.
                # And we accept that the Frontend might only show the FIRST cycle's logs unless we update Frontend to poll "latest session".
                # Wait! Frontend `AgentThinkingCard` has a poller:
                # `const res = await fetch(\`.../workflow/latest?symbol=BTC/USDT\`);`
                # This poller fetches the LATEST session logs!
                # So if we generate new IDs, the frontend WILL pick them up automatically!
                
                await self.run_workflow(symbol, current_session_id)
                
                # Workflow Loop Interval
                sleep_duration = settings.WORKFLOW_LOOP_INTERVAL 
                print(f"[Workflow] Cycle Complete. Sleeping for {sleep_duration}s...")
                
                # Sleep loop to allow faster cancellation
                for _ in range(sleep_duration):
                    if self.stop_signal: break
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                print("[Workflow] Loop Cancelled during sleep/run.")
                break
            except Exception as e:
                # Catch-all for any other errors to prevent loop death
                print(f"[Workflow] Loop Critical Error (Retrying in 10s): {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(10) # Retry delay
        
        self.is_running = False

    async def run_workflow(self, symbol: str, session_id: str = None):
        """
        Execute one full cycle of the Agent Workflow.
        Thread-safe: Skips execution if already running.
        """
        
        if self.processing_lock.locked():
            print(f"[Workflow] ⚠️ Skipped run: Engine is busy processing another trigger.")
            return

        async with self.processing_lock:
            if not session_id:
                session_id = str(uuid.uuid4())
            
            print(f"Starting Workflow Session: {session_id}", flush=True)

            # Create Session in DB with Retry
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.post(
                            f"{self.backend_url}/api/v1/workflow/session",
                            json={"session_id": session_id, "symbol": symbol}
                        )
                    break # Success
                except Exception as e:
                    if attempt == 2:
                        print(f"Warning: Failed to create session after 3 attempts: {e}", flush=True)
                    else:
                        await asyncio.sleep(1)

            try:
                # 1. Initialize State
                try:
                    account_balance = await self._fetch_account_balance_with_retry(retries=3, retry_delay=1.0)
                except Exception as e:
                    error_msg = str(e)
                    print(f"[Workflow] 🚨 CRITICAL: Failed to fetch account balance: {error_msg}", flush=True)
                    await self.analyst.emit_log(
                        content=f"🚨 CRITICAL RISK: Balance service unavailable. {error_msg}",
                        log_type="error",
                        session_id=session_id,
                        artifact={"reason": "balance_fetch_failed", "error": error_msg}
                    )
                    async with httpx.AsyncClient() as client:
                        await client.patch(
                            f"{self.backend_url}/api/v1/workflow/session/{session_id}",
                            json={"status": "FAILED", "review_status": "REJECTED"}
                        )
                    return None

                # --- 0. PRE-FLIGHT RISK CHECK ---
                if account_balance <= 0:
                    print(f"[Workflow] 🚨 CRITICAL: Negative Balance ({account_balance}). Aborting Analysis.", flush=True)
                    await self.analyst.emit_log(
                        content=f"🚨 CRITICAL RISK: Account Balance is Negative (${account_balance:.2f}). Trading Halted.",
                        log_type="error",
                        session_id=session_id,
                        artifact={"balance": account_balance}
                    )
                    # Fail session immediately
                    async with httpx.AsyncClient() as client:
                        await client.patch(
                            f"{self.backend_url}/api/v1/workflow/session/{session_id}",
                            json={"status": "FAILED", "review_status": "REJECTED"}
                        )
                    return None
                # -------------------------------

                # Fetch Positions
                positions = []
                try:
                    async with httpx.AsyncClient() as client:
                        res = await client.get(f"{self.backend_url}/api/v1/trade/positions")
                        if res.status_code == 200:
                            positions = res.json()
                except Exception as e:
                    print(f"Warning: Failed to fetch positions: {e}", flush=True)

                # Fetch Real Market Data via Service
                market_snapshot = market_data_service.get_full_snapshot(symbol)
                
                # Basic validation or fallback
                if market_snapshot["price"] == 0.0:
                    print(f"Warning: Could not fetch price for {symbol}, using fallback 65000.0", flush=True)
                    market_snapshot["price"] = 65000.0

                market_data = MarketData(
                    symbol=symbol,
                    timeframe="1m",
                    price=market_snapshot["price"], 
                    volume=market_snapshot["volume"],
                    indicators=market_snapshot["indicators"]
                )

                desired_notional = max(100.0, account_balance * 0.01)
                unresolved_todos = []
                ticker_depth = await market_intel_service.fetch_ticker_depth(symbol=symbol, levels=10)
                kline_1m = await market_intel_service.fetch_klines(symbol=symbol, interval="1m", limit=180)
                if not kline_1m:
                    unresolved_todos.append(f"{symbol} 缺少可用的 1m K线数据，使用基础模式运行")
                microstructure = market_intel_service.build_microstructure_snapshot(ticker_depth, desired_notional)
                regime = market_intel_service.classify_regime(kline_1m)
                portfolio_context = market_intel_service.build_portfolio_context(
                    account_balance=account_balance,
                    positions=positions,
                    mark_price=market_data.price,
                )
                execution_constraints = market_intel_service.build_execution_constraints(regime=regime, micro=microstructure)
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
                    unresolved_todos=unresolved_todos
                )
                
                await self.analyst.emit_log(
                    content=f"Workflow Initialized for {symbol}",
                    log_type="info",
                    session_id=session_id,
                    artifact={
                        "market_snapshot": market_data.dict(),
                        "balance": account_balance,
                        "positions": positions,
                        "market_regime": regime,
                        "microstructure": microstructure,
                        "portfolio_context": portfolio_context,
                        "execution_constraints": execution_constraints,
                        "safety_guard": safety,
                        "unresolved_todos": unresolved_todos,
                    }
                )
                if not safety.get("allowed", True):
                    await self.analyst.emit_log(
                        content=f"🚨 SAFETY_GUARD: {safety.get('reason')}. Session halted.",
                        log_type="error",
                        session_id=session_id,
                        artifact=safety,
                    )
                    # 业务级熔断(Kill Switch)不应算作系统运行失败(FAILED)
                    # 它是系统在极高风险下主动做出的安全决策，相当于一个强制的 "HOLD"
                    async with httpx.AsyncClient() as client:
                        await client.patch(
                            f"{self.backend_url}/api/v1/workflow/session/{session_id}",
                            json={"status": "COMPLETED", "review_status": "REJECTED"},
                        )
                    return None

                graph_inputs = {
                    "agent_state": state,
                    "session_id": session_id,
                    "symbol": symbol,
                    "completed_analysis": 0
                }
                
                config = {"configurable": {"thread_id": session_id}}
                
                print(f"--- Executing LangGraph Workflow for {session_id} ---", flush=True)
                
                final_state = None
                try:
                    # Run the graph
                    async for event in self.graph_app.astream(graph_inputs, config):
                        for node_name, output in event.items():
                            print(f"[Graph] Finished Node: {node_name}", flush=True)
                            # We can emit logs here if needed, but Agents already do it.
                            if "agent_state" in output:
                                final_state = output["agent_state"]
                except Exception as e:
                    print(f"LangGraph Execution Failed: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    # Fallback to failing the session
                    raise e

                if final_state:
                    state = final_state
                    
                print("Workflow Completed.", flush=True)
                
                # Update Session Status to COMPLETED with Decision Info
                try:
                    from datetime import datetime
                    update_payload = {
                        "status": "COMPLETED",
                        "end_time": datetime.utcnow().isoformat()
                    }
                    
                    if state.strategy_proposal:
                        update_payload["action"] = state.strategy_proposal.action
                        if state.strategy_proposal.action == "HOLD":
                            update_payload["review_status"] = "SKIPPED"
                        elif state.risk_verdict:
                            update_payload["review_status"] = "APPROVED" if state.risk_verdict.approved else "REJECTED"


                    async with httpx.AsyncClient() as client:
                        await client.patch(
                            f"{self.backend_url}/api/v1/workflow/session/{session_id}",
                            json=update_payload
                        )
                except Exception as e:
                    print(f"Warning: Failed to update session status: {e}", flush=True)

                return state
            except Exception as e:
                print(f"CRITICAL WORKFLOW ERROR: {e}", flush=True)
                import traceback
                traceback.print_exc()
                
                # Update Session Status to FAILED
                try:
                    if session_id:
                        async with httpx.AsyncClient() as client:
                            await client.patch(
                                f"{self.backend_url}/api/v1/workflow/session/{session_id}",
                                json={"status": "FAILED"}
                            )
                except Exception:
                    pass
                    
                return None

    async def close(self):
        await self.redis_client.close()
        await self.analyst.close()
        await self.strategist.close()
        await self.reviewer.close()
        await self.reflector.close()

if __name__ == "__main__":
    async def main():
        engine = WorkflowEngine()
        try:
            await engine.run_workflow("BTC/USDT", "test-session-1")
        finally:
            await engine.close()

    asyncio.run(main())
