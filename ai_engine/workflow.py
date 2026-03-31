import asyncio
import redis.asyncio as redis
import json
import uuid

from core.config import settings

from services.workflow_session_api import workflow_session_api
from services.workflow_runtime_api import workflow_runtime_api
from services.workflow_state_builder import workflow_state_builder
from services.workflow_loop_policy import workflow_loop_policy
from services.system_config import system_config_service

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
        
        # Continuous Mode State
        self.is_running = False
        self.stop_signal = False
        self.current_task = None
        self.latest_config = {}
        self.processing_lock = asyncio.Lock()
        
        self.reload_agents()

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
        orchestration_config = system_config_service.get_json("WORKFLOW_ORCHESTRATION_CONFIG")
        self.graph_app = create_trading_workflow(orchestration_config=orchestration_config)
        print("✅ Agents reloaded.")

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
                print("[Workflow] Current task cancelled during stop.", flush=True)
        self.is_running = False
        print(f"[Workflow] Loop Stopped.")

    async def _loop(self):
        while not self.stop_signal:
            try:
                symbol = self.latest_config.get("symbol")
                current_session_id = workflow_loop_policy.build_cycle_session_id(symbol)
                print(f"[Workflow] Starting Cycle for {symbol} (Session: {current_session_id})...")
                await self.run_workflow(symbol, current_session_id)
                sleep_duration = settings.WORKFLOW_LOOP_INTERVAL 
                print(f"[Workflow] Cycle Complete. Sleeping for {sleep_duration}s...")
                await workflow_loop_policy.sleep_interval(sleep_duration, lambda: self.stop_signal)
                    
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

            await workflow_session_api.create_session_with_retry(
                session_id=session_id,
                symbol=symbol,
                retries=3,
                retry_delay=1.0,
                timeout=5.0,
            )

            try:
                # 1. Initialize State
                try:
                    account_balance = await workflow_runtime_api.fetch_account_balance_with_retry(retries=3, retry_delay=1.0)
                except Exception as e:
                    error_msg = str(e)
                    print(f"[Workflow] 🚨 CRITICAL: Failed to fetch account balance: {error_msg}", flush=True)
                    await self.analyst.emit_log(
                        content=f"🚨 CRITICAL RISK: Balance service unavailable. {error_msg}",
                        log_type="error",
                        session_id=session_id,
                        artifact={"reason": "balance_fetch_failed", "error": error_msg}
                    )
                    await workflow_session_api.mark_rejected(session_id=session_id, failed=True)
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
                    await workflow_session_api.mark_rejected(session_id=session_id, failed=True)
                    return None
                # -------------------------------

                # Fetch Positions
                positions = await workflow_runtime_api.fetch_positions()

                state_build = await workflow_state_builder.build(
                    symbol=symbol,
                    session_id=session_id,
                    account_balance=account_balance,
                    positions=positions,
                )
                state = state_build.state
                safety = state_build.safety
                
                await self.analyst.emit_log(
                    content=f"Workflow Initialized for {symbol}",
                    log_type="info",
                    session_id=session_id,
                    artifact=state_build.artifact,
                )
                if not safety.get("allowed", True):
                    safety_reason = str(safety.get("reason") or "")
                    if safety_reason == "portfolio_leverage_too_high":
                        if state.execution_constraints is None:
                            state.execution_constraints = {}
                        state.execution_constraints["deleveraging_required"] = True
                        state.execution_constraints["reduce_only"] = True
                        state.execution_constraints["deleveraging_reason"] = "portfolio_leverage_too_high"
                        await self.analyst.emit_log(
                            content="⚠️ SAFETY_GUARD: portfolio_leverage_too_high. Continue in DELEVERAGING mode (strategy can only reduce risk).",
                            log_type="warning",
                            session_id=session_id,
                            artifact=safety,
                        )
                    else:
                        await self.analyst.emit_log(
                            content=f"🚨 SAFETY_GUARD: {safety_reason}. Session halted.",
                            log_type="error",
                            session_id=session_id,
                            artifact=safety,
                        )
                        await workflow_session_api.mark_completed(
                            session_id=session_id,
                            payload={"review_status": "REJECTED"},
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
                    update_payload = {
                    }
                    
                    if state.strategy_proposal:
                        update_payload["action"] = state.strategy_proposal.action
                        if state.strategy_proposal.action == "HOLD":
                            update_payload["review_status"] = "SKIPPED"
                        elif state.risk_verdict:
                            update_payload["review_status"] = "APPROVED" if state.risk_verdict.approved else "REJECTED"


                    await workflow_session_api.mark_completed(
                        session_id=session_id,
                        payload=update_payload,
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
                        await workflow_session_api.mark_failed(session_id=session_id)
                except Exception as mark_exc:
                    print(f"Warning: failed to mark session failed for {session_id}: {mark_exc}", flush=True)
                    
                return None

    async def close(self):
        await self.redis_client.close()
        await self.analyst.close()
        await self.sentiment_agent.close()
        await self.bull_strategist.close()
        await self.bear_strategist.close()
        await self.portfolio_manager.close()
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
