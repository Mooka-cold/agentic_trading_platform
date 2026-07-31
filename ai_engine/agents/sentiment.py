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

    def _infer_language(self, *parts: str) -> str:
        text = " ".join(str(part or "") for part in parts)
        return "zh" if any("\u4e00" <= ch <= "\u9fff" for ch in text) else "en"

    def _infer_source_tier(self, source_name: str) -> str:
        source = str(source_name or "unknown")
        weight = sentiment_service.source_weights.get(source, 0.75)
        if weight >= 0.9:
            return "top_tier"
        if weight >= 0.75:
            return "mainstream"
        return "secondary"

    async def _interpret_one_news(self, item: dict) -> dict:
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or "")
        language = str(item.get("language") or self._infer_language(title, summary))
        source_tier = str(item.get("source_tier") or self._infer_source_tier(str(item.get("source") or "unknown")))
        content_parts = [title]
        if summary and summary != title:
            content_parts.append(summary)
        content = "\n".join(content_parts)[:4000]
        result = await self.call_llm(
            prompt_vars={
                "news_id": str(item.get("news_id") or item.get("id") or ""),
                "published_at": str(item.get("published_at") or ""),
                "source_name": str(item.get("source") or "unknown"),
                "language": language,
                "title": title,
                "summary": summary,
                "content": content,
                "output_language": "zh"
            },
            state=None,
            output_model=NewsInterpretationOutput,
            prompt_name="sentiment_news_interpreter"
        )
        
        # Add basic fields back for backward compatibility with db/services.
        # call_llm returns a NewsInterpretationOutput Pydantic object (not a dict),
        # so convert to dict first before augmenting extra fields.
        result = result.model_dump()
        result["language"] = language
        result["source_tier"] = source_tier
        result["final_status"] = "verified" if not result.get("is_noise") else "insufficient_evidence"
        result["confidence"] = 1.0 if not result.get("is_noise") else 0.0
        result["magnitude"] = 0.5 if not result.get("is_noise") else 0.0
        result["severity"] = "medium" if not result.get("is_noise") else "low"
        result["bias"] = "neutral"
        result["cross_market_impacts"] = []
        result["asset_clusters"] = []
        result["impact_tags"] = []
        result["evidence_quotes"] = []

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
            pending = sentiment_service.claim_pending_interpretations(limit=50) # Compress up to 50 items
            if pending:
                await self._run_interpreter_batch(pending, concurrency=20)
                
            # Load compressed news from db
            compressed_rows = sentiment_service.load_interpreted_news(target_symbol=symbol, limit=20, lookback_hours=sentiment_window_hours)
            
            # Format compressed news for LLM context
            news_str_parts = []
            for row in compressed_rows:
                if row.get("final_status") != "insufficient_evidence":
                    news_str_parts.append(f"- [{row.get('source')}] {row.get('title')}: {row.get('summary_cn')}")
            news_str = "\n".join(news_str_parts) if news_str_parts else "No significant news."
            
            fear_greed_str = f"Index: {fng['value']} ({fng['classification']})"
            if fng.get("is_stale"):
                fear_greed_str = "[DATA STALE] " + fear_greed_str
            
        except Exception as e:
            await self.think(f"Data fetch failed: {e}", session_id)
            return {}

        # 2. Call LLM to produce the final compressed sentiment report
        try:
            result = await self.call_llm(
                prompt_vars={
                    "fear_greed_index": fear_greed_str,
                    "news_data": news_str,
                    "rule_context": "Rule engine disabled. Focus on compressing the news.",
                    "output_language": "zh"
                },
                state=state,
                output_model=SentimentOutput,
                prompt_name="sentiment"
            )
            
            fng_score = (float(fng.get("value", 50)) - 50.0) / 50.0
            llm_score = max(-1.0, min(1.0, float(result.get("llm_score", result.get("score", 0.0)))))
            
            report = SentimentOutput(
                score=llm_score,
                llm_score=llm_score,
                rule_score=fng_score,
                confidence=0.8,
                summary=str(result.get("summary", "")),
                key_drivers=list(result.get("key_drivers", [])),
                source_breakdown={},
                trade_gate="normal",
                sample_count=len(compressed_rows),
                aggregation_conflicts=[]
            )
            
            # 3. Output
            await self.say(
                f"NEWS COMPRESSED: {len(compressed_rows)} items. F&G: {fng['value']}. {report.summary}", 
                session_id,
                artifact={
                    "score": report.score,
                    "confidence": report.confidence,
                    "drivers": report.key_drivers,
                    "sample_count": report.sample_count,
                    "news_analysis": compressed_rows
                }
            )
            return {"sentiment_report": report}
            
        except Exception as e:
            await self.think(f"Sentiment analysis failed: {e}", session_id)
            return {}
