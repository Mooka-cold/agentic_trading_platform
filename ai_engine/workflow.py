import asyncio
import httpx
from typing import Dict, Any
from model.state import AgentState, MarketData, StrategyProposal, RiskVerdict
from agents.core import Analyst, Strategist, Reviewer, Reflector, SentimentAgent
import redis.asyncio as redis
import json
import os
import uuid

from core.config import settings

from services.market_data import market_data_service
from services.risk_checks import get_missing_proposal_fields

# Workflow Engine (Orchestrator)

class WorkflowEngine:
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.backend_url = settings.BACKEND_URL
        
        # Continuous Mode State
        self.is_running = False
        self.stop_signal = False
        self.current_task = None
        self.latest_config = {}
        self.processing_lock = asyncio.Lock()
        
        self.reload_agents()

    def reload_agents(self):
        print("🔄 Reloading Agents with latest config...")
        from agents.core import Analyst, Strategist, Reviewer, Reflector, SentimentAgent
        
        self.analyst = Analyst()
        self.sentiment_agent = SentimentAgent()
        self.strategist = Strategist()
        self.reviewer = Reviewer()
        self.reflector = Reflector()
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
                # Fetch Balance first
                account_balance = 0.0
                try:
                    async with httpx.AsyncClient() as client:
                        # Note: 'backend' service name
                        res = await client.get(f"{self.backend_url}/api/v1/trade/balance?currency=USDT")
                        if res.status_code == 200:
                            account_balance = float(res.json().get("balance", 0.0))
                except Exception as e:
                    print(f"Warning: Failed to fetch balance: {e}", flush=True)

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
                    indicators=market_snapshot["indicators"],
                    news_sentiment=0.0 # Will be updated by Sentiment Agent
                )
                
                state = AgentState(
                    session_id=session_id,
                    market_data=market_data,
                    account_balance=account_balance,
                    positions=positions
                )
                
                # --- LOG INITIAL CONTEXT ---
                # This helps debugging and historical review
                await self.analyst.emit_log(
                    content=f"Workflow Initialized for {symbol}",
                    log_type="info",
                    session_id=session_id,
                    artifact={
                        "market_snapshot": market_data.dict(),
                        "balance": account_balance,
                        "positions": positions
                    }
                )
                # ---------------------------

                # 2. Parallel Analysis (Analyst + Sentiment)
                # Use asyncio.gather to run Analyst and Sentiment agents concurrently
                await self.analyst.emit_log(
                    content="Initializing parallel analysis agents...",
                    log_type="info",
                    session_id=session_id
                )
                
                print("--- Analysis Phase ---", flush=True)
                # Wrap tasks in a way that exceptions are caught and logged properly
                analyst_task = self.analyst.run(state)
                sentiment_task = self.sentiment_agent.run(state)

                # Execute in parallel with return_exceptions=True to avoid one failure killing the other
                results = await asyncio.gather(analyst_task, sentiment_task, return_exceptions=True)
                
                for i, res in enumerate(results):
                    agent_name = "Analyst" if i == 0 else "Sentiment"
                    if isinstance(res, dict):
                        for k, v in res.items():
                            setattr(state, k, v)
                    elif isinstance(res, Exception):
                        print(f"[Workflow] {agent_name} Error: {res}", flush=True)
                        import traceback
                        traceback.print_exc()
                        await self.analyst.emit_log(
                            content=f"{agent_name} failed: {str(res)}",
                            log_type="error",
                            session_id=session_id
                        )

                # Check using correct attribute name 'analyst_report' matching AgentState definition
                if not getattr(state, "analyst_report", None):
                    await self.analyst.emit_log(
                        content="Analyst failed to produce report.",
                        log_type="error",
                        session_id=session_id
                    )
                    return None

                print("--- Strategist/Reviewer Negotiation ---", flush=True)
                max_revision_rounds = 2
                state.review_feedback = None
                state.strategy_revision_round = 0
                while True:
                    updates = await self.strategist.run(state)
                    for k, v in updates.items():
                        setattr(state, k, v)
                    missing_fields = get_missing_proposal_fields(state.strategy_proposal)
                    if missing_fields:
                        if state.strategy_revision_round >= max_revision_rounds:
                            state.risk_verdict = RiskVerdict(
                                approved=False,
                                risk_score=92.0,
                                message=f"Missing required proposal fields after revisions: {', '.join(missing_fields)}",
                                reject_code="MISSING_FIELDS",
                                fix_suggestions={"required_fields": missing_fields},
                                checks={"contract": "FAIL"}
                            )
                            await self.reviewer.say(
                                f"REJECTED [MISSING_FIELDS]. {state.risk_verdict.message}",
                                session_id,
                                artifact={
                                    "verdict": "REJECTED",
                                    "code": "MISSING_FIELDS",
                                    "fix_suggestions": state.risk_verdict.fix_suggestions
                                }
                            )
                            break
                        state.strategy_revision_round += 1
                        state.review_feedback = {
                            "reject_code": "MISSING_FIELDS",
                            "message": "Strategist output schema incomplete.",
                            "missing_fields": missing_fields,
                            "required_contract": ["action", "entry_price", "quantity", "stop_loss", "take_profit", "reasoning", "confidence", "assumptions"]
                        }
                        continue
                    updates = await self.reviewer.run(state)
                    for k, v in updates.items():
                        setattr(state, k, v)
                    verdict = state.risk_verdict
                    if not verdict or verdict.approved:
                        state.review_feedback = None
                        break
                    if state.strategy_revision_round >= max_revision_rounds:
                        break
                    if verdict.reject_code not in ["MISSING_FIELDS", "SL_DISTANCE_EXCEED", "RR_TOO_LOW", "DIRECTION_INVALID", "POLICY_REJECT"]:
                        break
                    state.strategy_revision_round += 1
                    state.review_feedback = {
                        "reject_code": verdict.reject_code,
                        "message": verdict.message,
                        "fix_suggestions": verdict.fix_suggestions,
                        "checks": verdict.checks
                    }
        
                # Check for POLICY_REJECT with Fix Suggestions
                if state.risk_verdict and not state.risk_verdict.approved:
                    # If Fix Suggestions are available and critical, emit specific alert
                    if state.risk_verdict.fix_suggestions and "deposit" in str(state.risk_verdict.fix_suggestions).lower():
                        await self.analyst.emit_log(
                            content="⚠️ CRITICAL: Reviewer suggests depositing funds. Automated notification sent.",
                            log_type="warning",
                            session_id=session_id
                        )
                        # Here we would integrate with a Notification Service (Email/Telegram)
                        # await self.notification_service.send_alert("Margin Call Risk: Please Deposit Funds")

                # 5. Step 4: Reflector
                print("--- Reflector Turn ---", flush=True)
                await self.reflector.run(state)

                print("Workflow Completed.", flush=True)
                
                # Update Session Status to COMPLETED with Decision Info
                try:
                    update_payload = {"status": "COMPLETED"}
                    
                    if state.strategy_proposal:
                        update_payload["action"] = state.strategy_proposal.action
                        if state.strategy_proposal.action == "HOLD":
                            update_payload["review_status"] = "SKIPPED"
                    
                    if state.risk_verdict:
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
