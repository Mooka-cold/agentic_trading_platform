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

class SentimentAgent(BaseAgent):
    def __init__(self):
        super().__init__("sentiment", "The Sentiment Analyst")

    async def _interpret_one_news(self, item: dict) -> dict:
        title = str(item.get("title") or "")
        summary = ""
        result = await self.call_llm(
            prompt_vars={
                "news_id": str(item.get("news_id") or item.get("id") or ""),
                "published_at": str(item.get("published_at") or ""),
                "source_name": str(item.get("source") or "unknown"),
                "source_tier": "mainstream",
                "language": "zh",
                "title": title,
                "summary": summary,
                "content": title
            },
            output_model=NewsInterpretationOutput,
            prompt_name="sentiment_news_interpreter"
        )
        result["magnitude"] = max(0.0, min(1.0, float(result.get("magnitude", 0.0))))
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        if "evidence_quotes" not in result or result["evidence_quotes"] is None:
            result["evidence_quotes"] = []
        if "noise_flags" not in result or result["noise_flags"] is None:
            result["noise_flags"] = []
        if "asset_mentions" not in result or result["asset_mentions"] is None:
            result["asset_mentions"] = []
        if "asset_clusters" not in result or result["asset_clusters"] is None:
            result["asset_clusters"] = []
        if "factor_tags" not in result or result["factor_tags"] is None:
            result["factor_tags"] = []
        if "impact_tags" not in result or result["impact_tags"] is None:
            result["impact_tags"] = []
        if "cross_market_impacts" not in result or result["cross_market_impacts"] is None:
            result["cross_market_impacts"] = []
        if "mapping_version" not in result or not result["mapping_version"]:
            result["mapping_version"] = "taxonomy_v1"
        normalized_impacts = []
        for impact in result["cross_market_impacts"]:
            if not isinstance(impact, dict):
                continue
            impact["magnitude"] = max(0.0, min(1.0, float(impact.get("magnitude", 0.0))))
            impact["confidence"] = max(0.0, min(1.0, float(impact.get("confidence", 0.0))))
            normalized_impacts.append(impact)
        result["cross_market_impacts"] = normalized_impacts
        normalized_tags = []
        for tag in result["impact_tags"]:
            if not isinstance(tag, dict):
                continue
            tag["magnitude"] = max(0.0, min(1.0, float(tag.get("magnitude", 0.0))))
            tag["confidence"] = max(0.0, min(1.0, float(tag.get("confidence", 0.0))))
            normalized_tags.append(tag)
        result["impact_tags"] = normalized_tags
        severity = str(result.get("severity") or "medium").lower()
        if len(result["evidence_quotes"]) == 0:
            result["final_status"] = "insufficient_evidence"
            if severity in {"high", "critical"}:
                result["severity"] = "medium"
            result["magnitude"] = min(float(result.get("magnitude", 0.0)), 0.55)
            result["confidence"] = min(float(result.get("confidence", 0.0)), 0.40)
        noise_flags = {str(x) for x in result.get("noise_flags", [])}
        if "no_primary_evidence" in noise_flags or "secondary_repost" in noise_flags:
            result["magnitude"] = min(float(result.get("magnitude", 0.0)), 0.55)
            result["confidence"] = min(float(result.get("confidence", 0.0)), 0.55)
        return result

    async def _run_interpreter_batch(self, pending_items: list[dict], concurrency: int = 20) -> dict:
        sem = asyncio.Semaphore(concurrency)
        stats = {"success": 0, "failed": 0}

        async def worker(item: dict):
            async with sem:
                try:
                    output = await self._interpret_one_news(item)
                    sentiment_service.mark_interpretation_success(str(item["news_id"]), output)
                    stats["success"] += 1
                except Exception as exc:
                    sentiment_service.mark_interpretation_failure(str(item["news_id"]), str(exc))
                    stats["failed"] += 1

        await asyncio.gather(*[worker(x) for x in pending_items], return_exceptions=True)
        return stats

    async def run_news_interpreter_cycle(self, symbol: str = "BTC/USDT", claim_limit: int = 200, concurrency: int = 20) -> dict:
        window_hours = int(getattr(sentiment_service, "news_window_hours", 6) or 6)
        news = await sentiment_service.get_latest_news(
            symbol,
            limit=800,
            trigger_fetch=False,
            within_hours=window_hours
        )
        queued = sentiment_service.queue_recent_news_for_interpretation(news)
        pending = sentiment_service.claim_pending_interpretations(limit=claim_limit)
        if not pending:
            return {"queued": queued, "claimed": 0, "success": 0, "failed": 0}
        stats = await self._run_interpreter_batch(pending, concurrency=concurrency)
        return {"queued": queued, "claimed": len(pending), **stats}

    async def run_daily_review(self, symbol: str = "BTC/USDT"):
        session_id = f"review-{datetime.now().strftime('%Y%m%d')}"
        await self.think(f"Daily review is handled by reflector pipeline, skip sentiment review for {symbol}.", session_id)
        return {"status": "skipped", "owner": "reflector", "symbol": symbol, "session_id": session_id}

    async def run(self, state: AgentState) -> dict:
        from services.market_data import market_data_service
        session_id = state.session_id
        symbol = state.market_data.symbol
        sentiment_window_hours = int(getattr(sentiment_service, "news_window_hours", 6) or 6)
        
        await self.think(f"Scanning news & social sentiment for {symbol}...", session_id)
        
        # 1. Fetch Data
        try:
            fng = await sentiment_service.get_fear_greed_index()
            if not fng:
                await self.think("⚠️ WARNING: Fear & Greed API failed or returned empty data.", session_id, log_type="error")
                fng = {"value": 50, "classification": "Neutral", "is_stale": True}
            elif fng.get("is_stale"):
                await self.think("⚠️ WARNING: Fear & Greed data is STALE (>48h old).", session_id, log_type="error")
                
            news = await sentiment_service.get_latest_news(
                symbol,
                limit=600,
                trigger_fetch=False,
                within_hours=sentiment_window_hours
            )
            sentiment_service.queue_recent_news_for_interpretation(news)
            pending = sentiment_service.claim_pending_interpretations(limit=200)
            batch_stats = {"success": 0, "failed": 0}
            if pending:
                batch_stats = await self._run_interpreter_batch(pending, concurrency=20)
            aggregate = sentiment_service.aggregate_interpreted_news(
                symbol,
                fng,
                lookback_hours=sentiment_window_hours
            )
            rule_packet = sentiment_service.build_rule_packet(news[:100], fng)
            
            fear_greed_str = f"Index: {fng['value']} ({fng['classification']})"
            if fng.get("is_stale"):
                fear_greed_str = "[DATA STALE] " + fear_greed_str
            # Format news for LLM context
            news_str = "\n".join([
                f"- [{n['source']}] {n['title']} (Positive: {n['votes'].get('positive',0)})" 
                if isinstance(n, dict) else f"- {n}"
                for n in news
            ])
            rule_context = (
                f"RuleScore={aggregate['news_score']:.4f}, "
                f"RuleFallbackScore={rule_packet['rule_score']:.4f}, "
                f"FGIScore={rule_packet['fng_score']:.4f}, "
                f"Confidence={aggregate['confidence']:.4f}, "
                f"SourceBreakdown={json.dumps(aggregate['source_breakdown'], ensure_ascii=False)}, "
                f"InterpreterBatch={json.dumps(batch_stats, ensure_ascii=False)}"
            )
            
        except Exception as e:
            await self.think(f"Data fetch failed: {e}", session_id)
            return {}

        # 2. Call LLM
        try:
            result = await self.call_llm(
                prompt_vars={
                    "fear_greed_index": fear_greed_str,
                    "news_data": news_str,
                    "rule_context": rule_context
                },
                output_model=SentimentOutput
            )
            
            llm_score = max(-1.0, min(1.0, float(result.get("llm_score", result.get("score", 0.0)))))
            rule_score = max(-1.0, min(1.0, float(aggregate["score"])))
            final_score = max(-1.0, min(1.0, llm_score * 0.6 + rule_score * 0.4))
            llm_confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            blended_confidence = max(0.0, min(1.0, llm_confidence * 0.5 + float(aggregate["confidence"]) * 0.5))
            report = SentimentOutput(
                score=final_score,
                llm_score=llm_score,
                rule_score=rule_score,
                confidence=blended_confidence,
                summary=str(result.get("summary", "")),
                key_drivers=list(result.get("key_drivers", [])) or list(aggregate.get("drivers", [])),
                source_breakdown=aggregate["source_breakdown"],
                trade_gate=str(aggregate.get("trade_gate", "normal")),
                trigger_reason=aggregate.get("trigger_reason"),
                urgent_event=bool(aggregate.get("urgent_event", False)),
                sample_count=int(aggregate.get("sample_count", 0)),
                aggregation_conflicts=list(aggregate.get("conflicts", []))
            )
            
            # 3. Output
            await self.say(
                f"SENTIMENT: Score {report.score:.2f}. {report.summary}", 
                session_id,
                artifact={
                    "score": report.score,
                    "llm_score": report.llm_score,
                    "rule_score": report.rule_score,
                    "confidence": report.confidence,
                    "drivers": report.key_drivers,
                    "source_breakdown": report.source_breakdown,
                    "aggregation_conflicts": aggregate.get("conflicts", []),
                    "sample_count": aggregate.get("sample_count", 0),
                    "trigger_reason": aggregate.get("trigger_reason"),
                    "urgent_event": aggregate.get("urgent_event", False),
                    "trade_gate": aggregate.get("trade_gate", "normal"),
                    "sentiment_window_hours": sentiment_window_hours,
                    "news_analysis": news # Pass full news objects for frontend display
                }
            )
            return {"sentiment_report": report}
            
        except Exception as e:
            await self.think(f"Sentiment analysis failed: {e}", session_id)
            return {}
