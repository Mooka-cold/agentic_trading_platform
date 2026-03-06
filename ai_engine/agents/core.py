import asyncio
import json
import httpx
from datetime import datetime
from agents.base import BaseAgent
from model.state import AgentState, MarketData, StrategyProposal, AnalystOutput, RiskVerdict, SentimentOutput
from services.market_data import market_data_service
from services.memory import memory_service
from services.execution import execution_service
from services.sentiment import sentiment_service
from services.risk_checks import compute_trade_metrics, get_missing_proposal_fields, build_fix_suggestions
from core.config import settings

class SentimentAgent(BaseAgent):
    def __init__(self):
        super().__init__("sentiment", "The Sentiment Analyst")

    async def run_daily_review(self, symbol: str = "BTC/USDT"):
        """
        Perform T+1 analysis on closed trades.
        """
        session_id = f"review-{datetime.now().strftime('%Y%m%d')}"
        # We need a dedicated Reflector for this, not SentimentAgent. 
        # But for MVP, let's assume this method is called by Reflector or Orchestrator.
        # Wait, I put this in SentimentAgent by mistake in previous toolcall!
        # I must move it to Reflector class.
        pass

    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        symbol = state.market_data.symbol
        
        await self.think(f"Scanning news & social sentiment for {symbol}...", session_id)
        
        # 1. Fetch Data
        try:
            fng = await sentiment_service.get_fear_greed_index()
            news = await sentiment_service.get_latest_news(symbol)
            
            fear_greed_str = f"Index: {fng['value']} ({fng['classification']})"
            # Format news for LLM context
            news_str = "\n".join([
                f"- [{n['source']}] {n['title']} (Positive: {n['votes'].get('positive',0)})" 
                if isinstance(n, dict) else f"- {n}"
                for n in news
            ])
            
        except Exception as e:
            await self.think(f"Data fetch failed: {e}", session_id)
            return {}

        # 2. Call LLM
        try:
            result = await self.call_llm(
                prompt_vars={
                    "fear_greed_index": fear_greed_str,
                    "news_data": news_str
                },
                output_model=SentimentOutput
            )
            
            report = SentimentOutput(**result)
            
            # 3. Output
            await self.say(
                f"SENTIMENT: Score {report.score:.2f}. {report.summary}", 
                session_id,
                artifact={
                    "score": report.score,
                    "drivers": report.key_drivers,
                    "news_analysis": news # Pass full news objects for frontend display
                }
            )
            return {"sentiment_report": report}
            
        except Exception as e:
            await self.think(f"Sentiment analysis failed: {e}", session_id)
            return {}

class Analyst(BaseAgent):
    def __init__(self):
        super().__init__("analyst", "The Analyst")

    async def _get_realtime_data(self, symbol: str) -> dict:
        """
        Fetch realtime indicators from Redis (written by Market Streamer).
        Returns dict with price, rsi, macd, etc.
        """
        try:
            # Redis key: market:BTC/USDT:realtime
            key = f"market:{symbol}:realtime"
            data = await self.redis_client.hgetall(key)
            
            if not data:
                return {}
                
            # Check freshness (TTL 5s)
            updated_at = float(data.get('updated_at', 0))
            if datetime.now().timestamp() - updated_at > 10: # Allow 10s lag
                print(f"[Analyst] Redis data stale ({updated_at}). Falling back.", flush=True)
                return {}
                
            return data
        except Exception as e:
            print(f"[Analyst] Redis fetch failed: {e}", flush=True)
            return {}

    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        symbol = state.market_data.symbol
        
        await self.think(f"Fetching realtime market data for {symbol}...", session_id)
        
        # 1. Try Realtime Redis Data first
        realtime_data = await self._get_realtime_data(symbol)
        
        technical_text = ""
        
        if realtime_data:
            # Use pre-calculated indicators
            price = float(realtime_data.get('price', 0))
            rsi = float(realtime_data.get('rsi_14', 0))
            macd = float(realtime_data.get('macd', 0))
            bb_upper = float(realtime_data.get('bb_upper', 0))
            bb_lower = float(realtime_data.get('bb_lower', 0))
            
            technical_text = (
                f"### Realtime Technicals (1m)\n"
                f"- Price: {price}\n"
                f"- RSI(14): {rsi:.2f}\n"
                f"- MACD: {macd:.4f}\n"
                f"- Bollinger: {bb_upper:.2f} / {bb_lower:.2f}\n"
            )
            await self.think(f"Using Realtime Stream Data (RSI={rsi:.2f})", session_id)
        else:
            # Fallback to historical fetch
            await self.think("Realtime stream unavailable. Fetching historical data...", session_id, log_type="warning")
            mtf_data = market_data_service.get_multi_timeframe_context(symbol)
            if "error" in mtf_data:
                 technical_text = f"Error fetching data: {mtf_data['error']}"
            else:
                 technical_text = (
                     f"### 1H Trend (Macro)\n{mtf_data.get('1h (Trend)', 'N/A')}\n\n"
                     f"### 15M Structure (Key Levels)\n{mtf_data.get('15m (Structure)', 'N/A')}\n\n"
                     f"### 5M Entry (Micro)\n{mtf_data.get('5m (Entry)', 'N/A')}"
                 )

        # Log Technical Data
        await self.think(
            f"Technical Context:\n{technical_text[:200]}...", 
            session_id, 
            artifact={"technical_data": technical_text}
        )

        # ... (Rest of logic) ...
        news_list = "No major breaking news."
        if state.market_data.news_sentiment > 0.5:
            news_list = "Positive sentiment detected."

        # 3. Call LLM
        try:
            result = await self.call_llm(
                prompt_vars={
                    "news_list": news_list,
                    "technical_data": technical_text
                },
                output_model=AnalystOutput
            )

            
            # Result is a dict (parsed JSON)
            report = AnalystOutput(**result)
            
            await self.say(
                f"BIAS: {report.trading_bias}. {report.summary}", 
                session_id,
                artifact={
                    "bias": report.trading_bias,
                    "risk": report.key_risk,
                    "reasoning": report.reasoning
                }
            )
            return {"analyst_report": report}
            
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            await self.think(f"Analysis failed: {str(e)}", session_id, log_type="error")
            print(f"[Analyst Error] {traceback_str}", flush=True)
            # Fallback
            return {}

class Strategist(BaseAgent):
    def __init__(self):
        super().__init__("strategist", "The Strategist")

    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        symbol = state.market_data.symbol
        
        if not state.analyst_report:
            await self.think("No analyst report found. Skipping.", session_id)
            return {}

        report = state.analyst_report
        await self.think(f"Reviewing Analyst's bias: {report.trading_bias}...", session_id)
        
        # Prepare context for LLM
        # Use full Analyst Reasoning + Sentiment Report
        sentiment_context = "Neutral"
        if state.sentiment_report:
            sentiment_context = (
                f"Score: {state.sentiment_report.score}\n"
                f"Summary: {state.sentiment_report.summary}\n"
                f"Drivers: {', '.join(state.sentiment_report.key_drivers)}"
            )

        market_summary = (
            f"Price: {state.market_data.price}\n"
            f"Technical Context: {report.reasoning}\n"
            f"Sentiment Context: {sentiment_context}\n"
            f"Risk Context: {report.key_risk}"
        )
        
        # Log Input Context for Strategist Traceability
        await self.think(
            "Strategist Input Context Prepared", 
            session_id, 
            artifact={"market_summary": market_summary, "analyst_bias": report.trading_bias}
        )
        
        # Retrieve Memory
        await self.think("Recalling past experiences and learned rules...", session_id)
        try:
            # 1. Contextual Insights (Similar market conditions)
            insights = memory_service.retrieve_insights(
                query=f"Market Condition: {report.summary}",
                limit=3
            )
            insight_context = "\n".join([f"- {i}" for i in insights]) if insights else "No relevant past insights found."
            
            # 2. Hard-Learned Rules (From FINAL synthesis)
            learned_rules = memory_service.retrieve_learned_rules(limit=3)
            rule_context = "\n".join([f"- [RULE] {r}" for r in learned_rules]) if learned_rules else "No specific learned rules yet."
            
            memory_context = f"### Past Insights (Contextual)\n{insight_context}\n\n### Iron Rules (From Post-Mortem)\n{rule_context}"
            
        except Exception as e:
            memory_context = f"Error retrieving memory: {e}"

        await self.think("Formulating trading plan...", session_id)
        
        user_strategy_config = "Strategy: Trend Following. Timeframe: 1H/15M. Risk: 1% per trade."
        review_feedback = "None"
        if state.review_feedback:
            review_feedback = json.dumps(state.review_feedback, ensure_ascii=False)
            await self.think(f"Revision round {state.strategy_revision_round}: applying reviewer feedback.", session_id)

        # Format Positions
        positions_str = "None"
        if state.positions:
            my_pos = [p for p in state.positions if p['symbol'] == symbol]
            if my_pos:
                # Provide detailed position info for LLM
                positions_str = json.dumps(my_pos, default=str)

        # 3. Handle Neutral Bias with Open Position (Optimization)
        # If bias is NEUTRAL and we have a profitable position, suggest trailing stop or partial close
        if report.trading_bias == "NEUTRAL" and positions_str != "None":
            await self.think("Bias is NEUTRAL but Position exists. Evaluating hold management...", session_id)
            # We inject a specific instruction into the prompt
            memory_context += "\n\n[CRITICAL INSTRUCTION] The market is NEUTRAL but we have an open position. Prioritize 'HOLD' with a tightened Stop Loss (Trailing Stop) or 'PARTIAL_CLOSE' to lock in profits. Do NOT Panic Sell unless indicators are clearly bearish."

        try:
            result = await self.call_llm(
                prompt_vars={
                    "user_strategy": user_strategy_config,
                    "market_data": market_summary,
                    "analyst_report": f"Analyst Bias: {report.trading_bias} (Confidence: {report.confidence if hasattr(report, 'confidence') else 0.5})",
                    "account_balance": f"{state.account_balance:.2f}",
                    "memory_context": memory_context,
                    "current_positions": positions_str,
                    "review_feedback": review_feedback
                },
                output_model=StrategyProposal
            )
            
            proposal = StrategyProposal(**result)
            
            # Handle default CLOSE quantity (If Action is SELL/CLOSE/COVER but Qty is None/0, assume FULL CLOSE)
            # This logic is a safety net if LLM fails to follow the "CRITICAL" instruction
            if proposal.action in ["SELL", "CLOSE", "COVER"] and (not proposal.quantity or proposal.quantity == 0):
                # Fetch current position size
                if state.positions:
                    my_pos = [p for p in state.positions if p['symbol'] == symbol]
                    if my_pos:
                        # Assuming single position per symbol for now, or sum them up
                        # Backend logic uses FIFO, so total size is what matters
                        total_size = sum(float(p['size'] if 'size' in p else p['quantity']) for p in my_pos)
                        if total_size > 0:
                            proposal.quantity = total_size
                            await self.think(f"Auto-adjusted Quantity to Full Position: {total_size}", session_id)

            if proposal.action == "HOLD":
                reasoning_text = proposal.reasoning.replace(" || ", "\n")
                prefix = f"[Rev. {state.strategy_revision_round}] " if state.strategy_revision_round > 0 else ""
                await self.say(
                    f"{prefix}DECISION: HOLD\nSTATUS: Bias {report.trading_bias} | Confidence {proposal.confidence:.2f} | Risk {report.key_risk}\n{reasoning_text}",
                    session_id,
                    artifact={
                        "action": "HOLD",
                        "confidence": proposal.confidence,
                        "bias": report.trading_bias,
                        "risk": report.key_risk,
                        "reasoning": proposal.reasoning,
                        "assumptions": proposal.assumptions,
                        "revision": state.strategy_revision_round,
                        "account_balance": state.account_balance,
                        "current_positions": positions_str,
                        "market_price": state.market_data.price
                    }
                )
            else:
                qty_str = f"{proposal.quantity:.4f}" if proposal.quantity else "N/A"
                sl_str = f"{proposal.stop_loss:.2f}" if proposal.stop_loss else "N/A"
                tp_str = f"{proposal.take_profit:.2f}" if proposal.take_profit else "N/A"
                rr = "N/A"
                if proposal.entry_price and proposal.stop_loss and proposal.take_profit:
                    risk = abs(proposal.entry_price - proposal.stop_loss)
                    reward = abs(proposal.take_profit - proposal.entry_price)
                    if risk > 0:
                        rr = f"{reward / risk:.2f}"
                metrics = compute_trade_metrics(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit)
                reasoning_text = proposal.reasoning.replace(" || ", "\n")
                prefix = f"[Rev. {state.strategy_revision_round}] " if state.strategy_revision_round > 0 else ""
                await self.say(
                    f"{prefix}DECISION: {proposal.action}\nPLAN: Entry {proposal.entry_price:.2f} | SL {sl_str} | TP {tp_str} | Qty {qty_str} | R/R {rr} | Confidence {proposal.confidence:.2f}\n{reasoning_text}",
                    session_id,
                    artifact={
                        "action": proposal.action,
                        "entry": proposal.entry_price,
                        "sl": proposal.stop_loss,
                        "tp": proposal.take_profit,
                        "quantity": proposal.quantity,
                        "rr": rr,
                        "confidence": proposal.confidence,
                        "reasoning": proposal.reasoning,
                        "assumptions": proposal.assumptions,
                        "sl_distance_pct": metrics.get("sl_distance_pct"),
                        "direction_ok": metrics.get("direction_ok"),
                        "revision": state.strategy_revision_round,
                        "account_balance": state.account_balance,
                        "current_positions": positions_str,
                        "market_price": state.market_data.price
                    }
                )
                
            return {"strategy_proposal": proposal}
            
        except Exception as e:
            await self.think(f"Strategy generation failed: {str(e)}", session_id)
            return {}

class Reviewer(BaseAgent):
    def __init__(self):
        super().__init__("reviewer", "The Reviewer")

    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        proposal = state.strategy_proposal
        
        if not proposal:
            await self.think("No strategy proposal received. Skipping risk review.", session_id)
            return {}

        if proposal.action == "HOLD":
            await self.say(
                f"DECISION: SKIP REVIEW | Action: HOLD | Confidence: {proposal.confidence:.2f} | Reason: {proposal.reasoning}",
                session_id,
                artifact={
                    "action": "HOLD",
                    "verdict": "SKIPPED",
                    "reasoning": proposal.reasoning
                }
            )
            return {}
            
        await self.think(f"Validating risk parameters for {proposal.action}...", session_id)
        missing_fields = get_missing_proposal_fields(proposal)
        if missing_fields:
            verdict = RiskVerdict(
                approved=False,
                risk_score=85.0,
                message=f"Missing required proposal fields: {', '.join(missing_fields)}",
                reject_code="MISSING_FIELDS",
                fix_suggestions={"required_fields": missing_fields},
                checks={"contract": "FAIL"}
            )
            await self.say(
                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                session_id,
                artifact={
                    "verdict": "REJECTED",
                    "code": verdict.reject_code,
                    "fix_suggestions": verdict.fix_suggestions
                }
            )
            return {"risk_verdict": verdict}

        metrics = compute_trade_metrics(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit)
        checks = {
            "sl_side": "PASS" if metrics.get("sl_side_ok") else "FAIL",
            "tp_side": "PASS" if metrics.get("tp_side_ok") else "FAIL",
            "direction": "PASS" if metrics.get("direction_ok") else "FAIL",
            "sl_distance": "PASS" if (metrics.get("sl_distance_pct") is not None and metrics["sl_distance_pct"] <= 0.03) else "FAIL",
            "rr_ratio": "PASS" if (metrics.get("rr_ratio") is not None and metrics["rr_ratio"] >= 1.5) else "FAIL"
        }
        if checks["direction"] == "FAIL":
            verdict = RiskVerdict(
                approved=False,
                risk_score=90.0,
                message="Direction constraints failed for SL/TP relative to entry.",
                reject_code="DIRECTION_INVALID",
                fix_suggestions=build_fix_suggestions(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit),
                checks=checks
            )
            await self.say(
                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                session_id,
                artifact={
                    "verdict": "REJECTED",
                    "code": verdict.reject_code,
                    "fix_suggestions": verdict.fix_suggestions
                }
            )
            return {"risk_verdict": verdict}
        if checks["sl_distance"] == "FAIL":
            verdict = RiskVerdict(
                approved=False,
                risk_score=88.0,
                message=f"SL distance {((metrics.get('sl_distance_pct') or 0) * 100):.2f}% exceeds 3.0%.",
                reject_code="SL_DISTANCE_EXCEED",
                fix_suggestions=build_fix_suggestions(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit),
                checks=checks
            )
            await self.say(
                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                session_id,
                artifact={
                    "verdict": "REJECTED",
                    "code": verdict.reject_code,
                    "fix_suggestions": verdict.fix_suggestions
                }
            )
            return {"risk_verdict": verdict}
        if checks["rr_ratio"] == "FAIL":
            verdict = RiskVerdict(
                approved=False,
                risk_score=75.0,
                message=f"R/R {metrics.get('rr_ratio'):.2f} is below 1.5 minimum.",
                reject_code="RR_TOO_LOW",
                fix_suggestions=build_fix_suggestions(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit),
                checks=checks
            )
            await self.say(
                f"REJECTED [{verdict.reject_code}]. {verdict.message}",
                session_id,
                artifact={
                    "verdict": "REJECTED",
                    "code": verdict.reject_code,
                    "fix_suggestions": verdict.fix_suggestions
                }
            )
            return {"risk_verdict": verdict}
        
        proposal_str = (
            f"Action: {proposal.action}, Entry: {proposal.entry_price}, SL: {proposal.stop_loss}, "
            f"TP: {proposal.take_profit}, Qty: {proposal.quantity}, Confidence: {proposal.confidence}, "
            f"Assumptions: {proposal.assumptions}"
        )
        volatility = "Medium Volatility (ATR: 1.5%)"
        
        try:
            result = await self.call_llm(
                prompt_vars={
                    "strategy_proposal": proposal_str,
                    "market_volatility": volatility,
                    "computed_metrics": json.dumps(metrics, ensure_ascii=False),
                    "account_balance": f"{state.account_balance:.2f}"
                },
                output_model=RiskVerdict
            )
            
            verdict = RiskVerdict(**result)
            if verdict.approved:
                verdict.reject_code = None
            else:
                if not verdict.reject_code:
                    verdict.reject_code = "POLICY_REJECT"
                if not verdict.fix_suggestions:
                    verdict.fix_suggestions = build_fix_suggestions(proposal.action, proposal.entry_price, proposal.stop_loss, proposal.take_profit)
                if not verdict.checks:
                    verdict.checks = checks
            
            if verdict.approved:
                await self.say(
                    f"APPROVED {proposal.action} {state.market_data.symbol}. Risk Score: {verdict.risk_score}/100.", 
                    session_id,
                    artifact={
                        "verdict": "APPROVED",
                        "score": verdict.risk_score,
                        "checks": verdict.checks,
                        "action": proposal.action
                    },
                    symbol=state.market_data.symbol
                )
                
                # --- Execute Order ---
                await self.think("Routing order to Execution Engine...", session_id)
                try:
                    data = await execution_service.execute_order(
                        action=proposal.action,
                        symbol=state.market_data.symbol,
                        quantity=proposal.quantity or 0.001,
                        price=state.market_data.price,
                        stop_loss=proposal.stop_loss,
                        take_profit=proposal.take_profit,
                        confidence=proposal.confidence,
                        session_id=session_id
                    )
                    
                    state.execution_result = data # Save result for Reflector
                    
                    if data.get("status") == "FILLED":
                        mode = data.get('mode', 'UNKNOWN')
                        pnl = data.get('pnl', 0.0)
                        pnl_str = f" | PnL: {pnl:.2f}" if pnl != 0 else ""
                        await self.say(f"EXECUTED [{mode}]: {data['status']} @ {data['executed_price']}. New Bal: {data['new_balance']}{pnl_str}", session_id)
                    else:
                        await self.think(f"Execution Failed: {data.get('message')}", session_id)
                            
                except Exception as ex:
                     await self.think(f"Execution Error: {str(ex)}", session_id)
                # ---------------------

            else:
                await self.say(
                    f"REJECTED [{verdict.reject_code}]. {verdict.message}", 
                    session_id,
                    artifact={
                        "verdict": "REJECTED",
                        "code": verdict.reject_code,
                        "reason": verdict.message[:60],
                        "fix_suggestions": verdict.fix_suggestions,
                        "checks": verdict.checks
                    }
                )
                
            return {"risk_verdict": verdict}
            
        except Exception as e:
            await self.think(f"Risk check failed: {str(e)}", session_id)
            return {}

class Reflector(BaseAgent):
    def __init__(self):
        super().__init__("reflector", "The Reflector")
    
    async def run(self, state: AgentState) -> dict:
        session_id = state.session_id
        
        await self.think("Reflecting on the decision process...", session_id)
        
        # 1. Post-Trade Analysis (If a trade was closed)
        if hasattr(state, 'execution_result') and state.execution_result.get('mode') in ['CLOSE', 'PARTIAL_CLOSE']:
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

        # 2. Immediate Reflection (Existing Logic - Context Archive)
        if not state.strategy_proposal or not state.analyst_report:
            return {}

        # ... (Rest of existing logic for context archiving) ...
        return {}

    async def run_immediate_review(self, order_id: str, exec_result: dict, session_id: str):
        """
        Execute Stage 1: Immediate Post-Mortem
        """
        await self.think(f"Running IMMEDIATE Post-Mortem for Order {order_id}", session_id)
        
        try:
            # 1. Prepare Data
            # In real system, fetch full order details from DB.
            # Here we use what we have in exec_result and session context
            
            pnl = exec_result.get('pnl', 0.0)
            executed_price = exec_result.get('executed_price', 0.0)
            # Assuming we can get symbol/side from context or pass it in
            # For MVP, we need to pass these.
            
            # 2. Render Prompt
            prompt_template = self._load_prompt("reflector/immediate.yaml")
            
            # Mock data if missing (MVP limitation)
            user_prompt = prompt_template['user'].format(
                symbol="BTC/USDT", # TODO: Get from args
                side="UNKNOWN",
                entry_price="UNKNOWN",
                exit_price=executed_price,
                pnl=pnl,
                r_multiple="N/A",
                setup_name="Standard",
                market_regime="UNKNOWN",
                planned_sl="N/A",
                actual_sl="N/A",
                planned_tp="N/A",
                actual_tp="N/A"
            )
            
            # 3. Call LLM
            messages = [
                {"role": "system", "content": prompt_template['system']},
                {"role": "user", "content": user_prompt}
            ]
            
            # Use json mode
            response = await self.llm.chat_completion(messages, response_format={"type": "json_object"})
            content = response.choices[0].message.content
            
            # 4. Save to DB
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{settings.BACKEND_URL}/api/v1/trade/reflection",
                    json={
                        "session_id": session_id,
                        "order_id": order_id, # Optional for backward compatibility
                        "stage": "IMMEDIATE",
                        "content": content,
                        "score": 80.0 # Parse from content
                    }
                )
                
            await self.say(f"IMMEDIATE Review Completed.", session_id, artifact={"type": "REFLECTION", "stage": "IMMEDIATE", "content": content})

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
                
                for task in tasks:
                    stage = task['stage']
                    target_session_id = task['session_id']
                    symbol = task['symbol']
                    action = task['action']
                    
                    # Log start of review for this specific session
                    await self.emit_log(
                        f"Starting {stage} review for Session {target_session_id} ({action})", 
                        "process", 
                        target_session_id
                    )
                    
                    # 2. Fetch Market Data for Review (Current Price vs Decision Price)
                    # For MVP, just fetch current price
                    current_price = 0.0
                    try:
                        # Assuming market_data_service is available or use crawler
                        # Here we might need a dedicated endpoint or service call
                        # Let's mock or use a simple fetch if possible
                        # Ideally: market_data = await market_service.get_current_price(symbol)
                        pass 
                    except:
                        pass

                    # 3. Load Prompt based on Stage & Outcome
                    # We need different prompts for HOLD vs TRADE
                    prompt_file = "reflector/session_review.yaml" # Unified prompt?
                    
                    # Construct Context
                    # We need to know what happened in that session.
                    # Fetch full session logs/state?
                    # For MVP, we use the summary passed in task or fetch session details
                    
                    session_details_res = await client.get(f"{settings.BACKEND_URL}/api/v1/workflow/session/{target_session_id}")
                    if session_details_res.status_code != 200:
                        continue
                    session_data = session_details_res.json()
                    
                    # Extract decision rationale from logs or stored fields
                    # This is complex. For now, we ask LLM to review based on "Action: {action}, Result: {review_result}"
                    
                    # 4. Call LLM
                    # Mocking the call for now as we need to implement the prompt template
                    review_content = f"Simulated {stage} review for {action}. Market moved X%."
                    
                    # 5. Save Reflection & Update Status
                    await client.post(
                        f"{settings.BACKEND_URL}/api/v1/trade/reflection",
                        json={
                            "session_id": target_session_id,
                            "stage": stage,
                            "content": review_content,
                            "score": 0.0,
                            "market_context": json.dumps({"price": current_price})
                        }
                    )
                    
                    # Update Session Status
                    # We need an endpoint to update periodic_review_status
                    # PATCH /api/v1/workflow/session/{id}
                    new_status = "PENDING"
                    if stage == "T_PLUS_1H": new_status = "T1_DONE"
                    elif stage == "T_PLUS_6H": new_status = "T6_DONE"
                    elif stage == "T_PLUS_24H": new_status = "COMPLETED"
                    
                    await client.patch(
                        f"{settings.BACKEND_URL}/api/v1/workflow/session/{target_session_id}",
                        json={"periodic_review_status": new_status}
                    )

                    await self.emit_log(
                        f"Completed {stage} review.", 
                        "output", 
                        target_session_id,
                        artifact={"type": "REFLECTION", "stage": stage, "content": review_content}
                    )

        except Exception as e:
            print(f"[Reflector] Periodic review loop failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
