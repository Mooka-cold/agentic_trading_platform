import asyncio
import json
import httpx
import yaml
from pathlib import Path
from datetime import datetime
from redis import Redis  # Fix NameError
from agents.base import BaseAgent
from model.state import AgentState, MarketData, StrategyProposal, AnalystOutput, RiskVerdict, SentimentOutput, TrendFollowerOutput, MeanReversionOutput, VolatilityHunterOutput, NewsInterpretationOutput
from services.market_data import market_data_service
from services.memory import memory_service
from services.execution import execution_service
from services.sentiment import sentiment_service
from services.risk_checks import compute_trade_metrics, get_missing_proposal_fields, build_fix_suggestions
from core.config import settings

# Lazy import for services to avoid circular deps or init issues
# from services.market_data import market_data_service 
# from services.memory import memory_service
# from services.execution import execution_service

class Reflector(BaseAgent):
    def __init__(self, redis_client: Redis):
        super().__init__("reflector", "The Reflector")
        self.redis_client = redis_client

    def _store_learning(self, content: str, metadata: dict):
        try:
            if not content:
                return
            memory_service.add_insight(content=content, metadata=metadata)
        except Exception:
            return
        
    def _load_prompt(self, prompt_name: str) -> dict:
        """
        Manually load a prompt file from ai_engine/prompts/
        prompt_name: e.g. 'reflector/t_plus_1h.yaml'
        """
        try:
            base_path = Path(__file__).parent.parent / "prompts"
            prompt_path = base_path / prompt_name
            if not prompt_path.exists():
                print(f"[Reflector] Prompt file not found: {prompt_path}", flush=True)
                return None
            
            with open(prompt_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"[Reflector] Failed to load prompt {prompt_name}: {e}", flush=True)
            return None
    
    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        
        await self.think("Reflecting on the decision process...", session_id)
        
        # 1. Post-Trade Analysis (If a trade was closed)
        if hasattr(state, 'execution_result') and state.execution_result and state.execution_result.get('mode') in ['CLOSE', 'PARTIAL_CLOSE']:
            closed_session_id = state.execution_result.get('closed_session_id')
            pnl = state.execution_result.get('pnl', 0.0)
            
            # TRIGGER IMMEDIATE REVIEW
            try:
                # We need Order ID to link reflection
                # For MVP, assume execution_result has order_id
                order_id = state.execution_result.get('order_id') # Make sure ExecutionService returns this
                
                if order_id:
                    await self.run_immediate_review(order_id, state.execution_result, session_id)
                    
                    # Schedule future reviews
                    # For MVP, we can't easily schedule persistent tasks here without Celery/APScheduler.
                    # We will rely on an external "Watcher" or Cron that calls /workflow/review/periodic
                    # But we should log that this order needs future review.
                    # Ideally, store in DB: "pending_reviews" table? 
                    # Or simpler: The Cron job just scans for all orders closed > 1h ago that don't have T+1H reflection yet.
                    pass

            except Exception as e:
                await self.think(f"Immediate review failed: {e}", session_id)

        # 2. Immediate Reflection on Decision (NEW)
        # Even for OPEN or HOLD, we want to log a reflection on WHY we made this decision.
        if state.strategy_proposal:
            await self.run_decision_reflection(state, session_id)

        return {}

    async def run_decision_reflection(self, state: AgentState, session_id: str):
        """
        Reflect on the immediate decision (Buy/Sell/Hold) and the reasoning path.
        """
        action = state.strategy_proposal.action
        bias = state.analyst_report.trading_bias if state.analyst_report else "UNKNOWN"
        
        reflection_msg = f"Reflecting on decision to {action} (Bias: {bias})..."
        await self.think(reflection_msg, session_id)
        
        # Construct a simple self-critique prompt
        # For MVP, we'll just summarize the logic chain
        
        summary = (
            f"Decision: {action}\n"
            f"Analyst Bias: {bias}\n"
            f"Strategist Confidence: {state.strategy_proposal.confidence}\n"
            f"Risk Verdict: {'APPROVED' if state.risk_verdict and state.risk_verdict.approved else 'REJECTED'}"
        )
        
        # In a full system, we'd ask LLM: "Did I miss anything? Was this consistent?"
        # Here we just log it as a structured reflection artifact.
        
        await self.say(
            f"REFLECTION: Decision process for {action} archived.", 
            session_id,
            artifact={
                "type": "DECISION_REFLECTION",
                "summary": summary,
                "timestamp": datetime.now().isoformat()
            }
        )
        self._store_learning(
            content=f"{action} | {summary}",
            metadata={"type": "decision_reflection", "session_id": session_id, "symbol": state.market_data.symbol}
        )

    async def run_immediate_review(self, order_id: str, exec_result: dict, session_id: str):
        """
        Execute Stage 1: Immediate Post-Mortem
        """
        await self.think(f"Running IMMEDIATE Post-Mortem for Order {order_id}", session_id)
        
        try:
            # 1. Prepare Data
            prompt_def = self._load_prompt("reflector/immediate.yaml")
            if not prompt_def:
                return
            
            # We need context: Was this a forced exit? Or TP/SL?
            # session_id usually has info like "guardian-stop_loss"
            exit_reason = "MANUAL_CLOSE"
            if "guardian-stop_loss" in session_id:
                exit_reason = "STOP_LOSS_HIT"
            elif "guardian-take_profit" in session_id:
                exit_reason = "TAKE_PROFIT_HIT"
            elif "guardian" in session_id:
                exit_reason = "GUARDIAN_FORCE_CLOSE"
            
            pnl = exec_result.get("pnl", 0.0)
            
            # 2. Call LLM
            from langchain_core.messages import SystemMessage, HumanMessage
            system_msg = str(prompt_def.get("system", "You are a disciplined Trading Coach conducting an IMMEDIATE POST-MORTEM (T+0)."))
            user_tpl = str(prompt_def.get("user", ""))
            prompt_vars = {
                "symbol": str(exec_result.get("symbol", "BTC/USDT")),
                "side": str(exec_result.get("side", "UNKNOWN")),
                "entry_price": exec_result.get("entry_price", 0.0),
                "exit_price": exec_result.get("exit_price", 0.0),
                "pnl": f"{float(pnl):.2f}",
                "r_multiple": exec_result.get("r_multiple", 0.0),
                "setup_name": str(exec_result.get("setup_name", "UNKNOWN")),
                "market_regime": str(exec_result.get("market_regime", "UNKNOWN")),
                "planned_sl": exec_result.get("planned_sl", "N/A"),
                "actual_sl": exec_result.get("actual_sl", "N/A"),
                "planned_tp": exec_result.get("planned_tp", "N/A"),
                "actual_tp": exec_result.get("actual_tp", "N/A")
            }
            try:
                user_msg = user_tpl.format(**prompt_vars)
            except Exception:
                user_msg = (
                    f"Order ID: {order_id}\n"
                    f"Exit Reason: {exit_reason}\n"
                    f"PnL: {pnl:.2f}\n"
                    f"Session ID: {session_id}"
                )
            
            messages = [
                SystemMessage(content=f"{system_msg}\nAll explanatory text must be in {self.output_language}. Keep JSON keys in English."),
                HumanMessage(content=user_msg)
            ]
            
            result = await self.llm.ainvoke(messages)
            content = result.content
            
            # 3. Parse JSON (Heuristic)
            import json
            try:
                # Extract JSON block
                json_str = content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0]
                
                reflection_data = json.loads(json_str)
                
                # 4. Save to DB
                # We need to call backend API to save reflection
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{settings.BACKEND_URL}/api/v1/workflow/reflection",
                        json={
                            "session_id": session_id, # Link to this session
                            "stage": "IMMEDIATE",
                            "score": reflection_data.get("execution_score", 0),
                            "content": json.dumps(reflection_data)
                        }
                    )
                
                await self.say(
                    f"POST-MORTEM: {reflection_data.get('conclusion', 'Analysis complete')}",
                    session_id,
                    artifact=reflection_data
                )
                learning_text = reflection_data.get("learned_rule") or reflection_data.get("conclusion") or ""
                self._store_learning(
                    content=str(learning_text),
                    metadata={
                        "type": "learned_rule",
                        "session_id": session_id,
                        "stage": "IMMEDIATE"
                    }
                )
                
            except Exception as e:
                print(f"[Reflector] Failed to parse/save reflection: {e}", flush=True)

        except Exception as e:
            await self.think(f"Immediate review logic failed: {e}", session_id)

    async def run_periodic_reviews(self):
        """
        Called by Cron to check for sessions needing 1H, 6H, 24H reviews.
        """
        session_id_log = f"periodic-review-{int(datetime.now().timestamp())}"
        # Use a temporary session ID for the logs of the review process itself
        
        try:
            async with httpx.AsyncClient() as client:
                # 1. Fetch Pending Reviews
                # Backend returns list of {session_id, symbol, stage, action, review_result, end_time}
                res = await client.get(f"{settings.BACKEND_URL}/api/v1/trade/reflection/pending")
                if res.status_code != 200:
                    print(f"Failed to fetch pending reviews: {res.text}", flush=True)
                    return
                
                tasks = res.json()
                if not tasks:
                    return

                print(f"[Reflector] Found {len(tasks)} pending review tasks.", flush=True)
                
                # BATCH PROCESSING LIMIT
                # To prevent overloading LLM or getting timed out, limit to 5 tasks per cycle.
                # Implement Redis Lock for each task
                # Key: "lock:reflector:{session_id}"
                # TTL: 10 minutes (to prevent deadlocks)
                
                # Increase batch size to clear backlog faster
                tasks_to_process = tasks[:100]
                
                for task in tasks_to_process:
                    try:
                        target_session_id = task['session_id']
                        
                        # Acquire Lock
                        lock_key = f"lock:reflector:{target_session_id}"
                        # Check if already locked
                        # Note: redis_client is redis.Redis (async or sync?)
                        # In WorkflowEngine.__init__, we used redis.from_url(..., decode_responses=True)
                        # The standard redis-py client is synchronous unless we use redis.asyncio
                        
                        # Let's check imports or assume sync if it was working before for simple get/set.
                        # BUT, the error says: RuntimeWarning: coroutine 'Redis.execute_command' was never awaited
                        # This means self.redis_client IS an async client!
                        
                        is_locked = await self.redis_client.get(lock_key)
                        if is_locked:
                            # print(f"[Reflector] Skipping {target_session_id} (Locked)", flush=True)
                            continue
                            
                        # Set Lock (NX=Not Exists, EX=Expire 600s)
                        if not await self.redis_client.set(lock_key, "PROCESSING", ex=600, nx=True):
                            continue
                            
                        stage = task['stage']
                        symbol = task['symbol']
                        action = task['action']
                        
                        # Log start of review for this specific session
                        await self.emit_log(
                            f"Starting {stage} review for Session {target_session_id} ({action})", 
                            "process", 
                            target_session_id
                        )
                        
                        # 2. Fetch Session Details
                        session_details_res = await client.get(f"{settings.BACKEND_URL}/api/v1/workflow/session/{target_session_id}")
                        session_data = {}
                        if session_details_res.status_code == 200:
                            session_data = session_details_res.json().get('session', {})
                        
                        review_status = session_data.get('review_status', 'UNKNOWN')

                        # 3. Fetch Market Data for Review
                        current_price = 0.0
                        change_pct = 0.0
                        try:
                            snapshot = market_data_service.get_full_snapshot(symbol)
                            current_price = snapshot.get('price', 0.0)
                        except Exception as me:
                            print(f"[Reflector] Market fetch failed: {me}", flush=True)

                        # 4. Select Prompt & Prepare Context
                        # Unified Prompt Strategy: Always use 'session_review.yaml' with full logs
                        prompt_name = "reflector/session_review.yaml"
                        
                        # Fetch full session logs for context
                        logs_context = "Logs unavailable."
                        try:
                            log_res = await client.get(f"{settings.BACKEND_URL}/api/v1/workflow/session/{target_session_id}/logs")
                            if log_res.status_code == 200:
                                logs_data = log_res.json().get('logs', [])
                                # Format logs for LLM
                                logs_context = "\n".join([
                                    f"[{l['timestamp']}] {l['agent'].upper()}: {l['type']} - {l['content'][:500]}" # Truncate long content
                                    for l in logs_data
                                ])
                        except Exception as le:
                            print(f"[Reflector] Log fetch failed: {le}", flush=True)

                        prompt_vars = {
                            "session_id": target_session_id,
                            "symbol": symbol,
                            "stage": stage,
                            "final_status": review_status, # REJECTED / COMPLETED
                            "current_price": f"{current_price:.2f}",
                            "change_pct": f"{change_pct:.2f}",
                            "session_logs": logs_context
                        }
                        
                        # 5. Call LLM
                        content = ""
                        try:
                            # Use load_prompt and call_llm
                            # We can reuse BaseAgent.call_llm but need to support custom prompt name
                            # call_llm takes prompt_vars and output_model.
                            # But T_PLUS_1H output is complex JSON.
                            
                            # Let's do a direct call similar to run_immediate_review
                            prompt_def = self._load_prompt(prompt_name)
                            if prompt_def:
                                system_msg = prompt_def.get("system", "You are a crypto trading analyst.")
                                user_msg = prompt_def.get("user", "").format(**prompt_vars) if prompt_vars else f"Review {stage} for {action}"
                                
                                from langchain_core.messages import SystemMessage, HumanMessage
                                messages = [
                                    SystemMessage(content=f"{system_msg}\nAll explanatory text must be in {self.output_language}. Keep JSON keys in English."),
                                    HumanMessage(content=user_msg)
                                ]
                                
                                # Use ainvoke with json binding
                                # llm_json = self.llm.bind(response_format={"type": "json_object"})
                                # response = await llm_json.ainvoke(messages)
                                # content = response.content
                                # FIX: bind() method might not be available on all LLM wrappers or versions.
                                # Use standard invoke and parse.
                                response = await self.llm.ainvoke(messages)
                                content = response.content
                            else:
                                content = json.dumps({"conclusion": f"Simulated {stage} review for {action}."})
                                
                        except Exception as llm_e:
                            print(f"[Reflector] LLM failed: {llm_e}", flush=True)
                            content = json.dumps({"error": str(llm_e), "stage": stage})

                        # 6. Save Reflection & Update Status
                        await client.post(
                            f"{settings.BACKEND_URL}/api/v1/trade/reflection",
                            json={
                                "session_id": target_session_id,
                                "stage": stage,
                                "content": content,
                                "score": 0.0,
                                "market_context": json.dumps({"price": current_price})
                            }
                        )
                        self._store_learning(
                            content=content[:1200],
                            metadata={
                                "type": "periodic_reflection",
                                "session_id": target_session_id,
                                "stage": stage,
                                "symbol": symbol
                            }
                        )
                        
                        # Update Session Status
                        new_status = "PENDING"
                        if stage == "T_PLUS_1H": new_status = "T1_DONE"
                        elif stage == "T_PLUS_6H": new_status = "T6_DONE"
                        elif stage == "T_PLUS_24H": new_status = "COMPLETED"
                        
                        patch_res = await client.patch(
                            f"{settings.BACKEND_URL}/api/v1/workflow/session/{target_session_id}",
                            json={"periodic_review_status": new_status}
                        )
                        if patch_res.status_code != 200:
                            print(f"[Reflector] WARNING: Failed to update status for {target_session_id}: {patch_res.text}", flush=True)

                        # Release Lock
                        await self.redis_client.delete(f"lock:reflector:{target_session_id}")

                        await self.emit_log(
                            f"Completed {stage} review.", 
                            "output", 
                            target_session_id,
                            artifact={"type": "REFLECTION", "stage": stage, "content": content}
                        )
                        
                    except Exception as task_e:
                        print(f"[Reflector] Task {task.get('session_id')} failed: {task_e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        # Continue to next task!

        except Exception as e:
            print(f"[Reflector] Periodic review loop failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
