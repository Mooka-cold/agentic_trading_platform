import httpx
import asyncio
import hashlib
import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from core.config import settings
from services.system_config import system_config_service
from model.policies import DataRoutingPolicy

class SentimentService:
    def __init__(self):
        self.fear_greed_url = "https://api.alternative.me/fng/?limit=1"
        self.backend_url = settings.BACKEND_URL
        # Connect to User DB to fetch News (Fallback)
        self.engine = create_engine(settings.DATABASE_USER_URL)
        self.source_weights = {
            "TechFlow-OnchainWhale": 1.25,
            "TechFlow-Newsletter": 1.0,
            "CryptoPanic": 0.95,
            "CoinDesk": 0.9,
            "Cointelegraph": 0.9
        }
        self.bullish_keywords = [
            "adoption", "partnership", "launch", "approval", "inflow", "buy", "long",
            "增持", "加仓", "买入", "做多", "净流入", "突破", "利好"
        ]
        self.bearish_keywords = [
            "hack", "exploit", "ban", "outflow", "sell", "short", "liquidation", "rate hike",
            "减持", "卖出", "做空", "平仓", "清算", "爆仓", "净流出", "利空", "监管打击"
        ]
        self.interpreter_version = "v1"
        self.max_retry = 5
        self._schema_ready = False
        self.quality_confidence_floor = 0.35
        self.major_event_confidence_floor = 0.55
        self.exclude_insufficient_evidence = True
        self.exclude_low_severity = True
        self.min_magnitude_floor = 0.35
        self.relevance_weights = {
            "cluster_match": 1.0,
            "impact_cluster_match": 0.9,
            "symbol_match": 0.95,
            "symbol_cluster_match": 0.85,
            "unknown_general": 0.6,
            "macro_only": 0.75,
            "other_related": 0.4
        }
        self.taxonomy_version = "taxonomy_v1"
        self.news_window_hours = 6
        self.cluster_defaults = {
            "CRYPTO_MAJOR": {"weight": 1.0},
            "CRYPTO_L1": {"weight": 0.9},
            "CRYPTO_DEFI": {"weight": 0.75},
            "STABLECOIN": {"weight": 0.8},
            "EQUITY_CRYPTO_PROXY": {"weight": 0.65},
            "MACRO": {"weight": 0.7}
        }
        self.reload_tuning_from_system_config()

    def _normalize_tuning_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged = {
            "quality_confidence_floor": 0.35,
            "major_event_confidence_floor": 0.55,
            "exclude_insufficient_evidence": True,
            "exclude_low_severity": True,
            "min_magnitude": 0.35,
            "relevance_weights": dict(self.relevance_weights)
        }
        if isinstance(params, dict):
            for k in ["quality_confidence_floor", "major_event_confidence_floor", "exclude_insufficient_evidence", "exclude_low_severity", "min_magnitude"]:
                if k in params:
                    merged[k] = params[k]
            rw = params.get("relevance_weights")
            if isinstance(rw, dict):
                for rk in merged["relevance_weights"].keys():
                    if rk in rw:
                        merged["relevance_weights"][rk] = rw[rk]
        merged["quality_confidence_floor"] = max(0.0, min(0.95, float(merged["quality_confidence_floor"])))
        merged["major_event_confidence_floor"] = max(0.0, min(1.0, float(merged["major_event_confidence_floor"])))
        merged["min_magnitude"] = max(0.0, min(1.0, float(merged["min_magnitude"])))
        merged["exclude_insufficient_evidence"] = bool(merged["exclude_insufficient_evidence"])
        merged["exclude_low_severity"] = bool(merged["exclude_low_severity"])
        for rk, rv in list(merged["relevance_weights"].items()):
            merged["relevance_weights"][rk] = max(0.0, min(1.2, float(rv)))
        return merged

    def apply_tuning_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        normalized = self._normalize_tuning_params(params)
        self.quality_confidence_floor = float(normalized["quality_confidence_floor"])
        self.major_event_confidence_floor = float(normalized["major_event_confidence_floor"])
        self.exclude_insufficient_evidence = bool(normalized["exclude_insufficient_evidence"])
        self.exclude_low_severity = bool(normalized["exclude_low_severity"])
        self.min_magnitude_floor = float(normalized["min_magnitude"])
        self.relevance_weights = dict(normalized["relevance_weights"])
        return normalized

    def reload_tuning_from_system_config(self) -> Dict[str, Any]:
        query = text("SELECT value FROM system_configs WHERE key = :key LIMIT 1")
        try:
            with self.engine.connect() as conn:
                tuning_row = conn.execute(query, {"key": "SENTIMENT_TUNING_PARAMS"}).first()
                window_row = conn.execute(query, {"key": "SENTIMENT_NEWS_WINDOW_HOURS"}).first()
            if window_row and window_row[0]:
                try:
                    self.news_window_hours = max(1, min(72, int(str(window_row[0]).strip())))
                except Exception:
                    self.news_window_hours = 6
            else:
                self.news_window_hours = 6
            if tuning_row and tuning_row[0]:
                loaded = json.loads(tuning_row[0])
                normalized = self.apply_tuning_params(loaded)
                normalized["news_window_hours"] = self.news_window_hours
                return normalized
        except Exception as e:
            print(f"[Sentiment] Load tuning params failed: {e}")
        self.news_window_hours = 6
        normalized = self.apply_tuning_params(None)
        normalized["news_window_hours"] = self.news_window_hours
        return normalized

    def get_active_tuning_params(self) -> Dict[str, Any]:
        return {
            "quality_confidence_floor": self.quality_confidence_floor,
            "major_event_confidence_floor": self.major_event_confidence_floor,
            "exclude_insufficient_evidence": self.exclude_insufficient_evidence,
            "exclude_low_severity": self.exclude_low_severity,
            "min_magnitude": self.min_magnitude_floor,
            "relevance_weights": dict(self.relevance_weights),
            "news_window_hours": self.news_window_hours
        }

    async def get_fear_greed_index(self) -> Dict:
        """
        Fetch Fear & Greed Index from Alternative.me
        Returns: {value: int, classification: str, is_stale: bool}
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.fear_greed_url)
                if resp.status_code == 200:
                    data = resp.json()
                    item = data['data'][0]
                    
                    # Check freshness
                    timestamp = int(item.get('timestamp', 0))
                    import time
                    is_stale = False
                    if timestamp > 0:
                        # If data is older than 48 hours (F&G updates daily)
                        if time.time() - timestamp > 48 * 3600:
                            is_stale = True
                            
                    return {
                        "value": int(item['value']),
                        "classification": item['value_classification'],
                        "is_stale": is_stale
                    }
        except Exception as e:
            print(f"[Sentiment] Fear & Greed fetch failed: {e}")
        
        # Don't mock silently. Return None so agent knows it failed.
        return None

    async def get_latest_news(self, symbol: str = "BTC", limit: int = 10, trigger_fetch: bool = True, within_hours: Optional[int] = None) -> List[Dict]:
        """
        Trigger Backend to fetch latest news, then read from DB.
        """
        routing_policy = DataRoutingPolicy(**(system_config_service.get_json("DATA_ROUTING_POLICY") or {}))
        news_policy = routing_policy.news
        timeout_sec = max(1.0, float(news_policy.timeout_ms) / 1000.0)
        # 1. Trigger Fetch
        fetch_failed = False
        if trigger_fetch:
            try:
                async with httpx.AsyncClient(timeout=timeout_sec) as client:
                    resp = await client.post(f"{self.backend_url}/api/v1/news/fetch", params={"symbol": symbol})
                    if resp.status_code != 200:
                        fetch_failed = True
                        print(f"[Sentiment] Warning: News fetch API returned {resp.status_code}")
            except Exception as e:
                fetch_failed = True
                print(f"[Sentiment] Warning: Failed to trigger news fetch: {e}")

        # 2. Read from DB
        filter_hours = max(1, int(within_hours)) if within_hours is not None else None
        if filter_hours is not None:
            query = text("""
                SELECT id, title, source, published_at, url, summary
                FROM news
                WHERE published_at >= NOW() - (:within_hours || ' hours')::interval
                ORDER BY published_at DESC
                LIMIT :limit
            """)
            params = {"limit": limit, "within_hours": filter_hours}
        else:
            query = text("""
                SELECT id, title, source, published_at, url, summary
                FROM news
                ORDER BY published_at DESC
                LIMIT :limit
            """)
            params = {"limit": limit}
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query, params).fetchall()
            
            news_items = []
            if result:
                # Parse votes from summary if possible, or mock
                # Our backend crawler stores votes string in summary: "Votes: +10/-2"
                # BUT NewsAPI stores actual description in summary.
                
                for row in result:
                    votes = {"positive": 0, "negative": 0}
                    # If summary looks like votes, parse it (legacy CryptoPanic)
                    if row.summary and "Votes:" in row.summary:
                        try:
                            parts = row.summary.replace("Votes: ", "").split("/")
                            if len(parts) == 2:
                                votes["positive"] = int(parts[0].replace("+", ""))
                                votes["negative"] = int(parts[1].replace("-", ""))
                        except Exception as parse_exc:
                            print(f"[Sentiment] Votes parse failed for news {row.id}: {parse_exc}")
                    
                    news_items.append({
                        "id": str(row.id),
                        "title": row.title,
                        "source": row.source,
                        "published_at": str(row.published_at),
                        "domain": row.source, 
                        "url": row.url,
                        "votes": votes,
                        "summary": row.summary # Pass summary to Agent if needed
                    })
            
            # Inject warning if fetch failed and we have no fresh data
            if fetch_failed and (not news_items or filter_hours is not None):
                news_items.insert(0, {
                    "id": "system_warning",
                    "title": "⚠️ SYSTEM WARNING: Failed to fetch latest news from external sources. The following data might be stale or empty.",
                    "source": "System",
                    "published_at": "",
                    "domain": "System",
                    "url": "",
                    "votes": {"positive": 0, "negative": 0},
                    "summary": ""
                })
                
            return news_items
            
        except Exception as e:
            print(f"[Sentiment] DB fetch failed: {e}")
            return []

    async def get_combined_sentiment(self, symbol: str) -> str:
        """
        Aggregates data for the Sentiment Agent.
        """
        fng = await self.get_fear_greed_index()
        news = await self.get_latest_news(symbol)
        
        # Format news objects into a string for the LLM
        news_str = "\n".join([
            f"- [{n['source']}] {n['title']} (Votes: +{n['votes'].get('positive',0)}/-{n['votes'].get('negative',0)})" 
            if isinstance(n, dict) else f"- {n}" 
            for n in news
        ])
        
        context = (
            f"Market Sentiment (Fear & Greed): {fng['value']} ({fng['classification']})\n"
            f"Latest News Headlines:\n{news_str}"
        )
        return context

    def _ensure_interpretation_schema(self):
        if self._schema_ready:
            return
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS news_interpretations (
                id BIGSERIAL PRIMARY KEY,
                news_id UUID UNIQUE NOT NULL,
                title TEXT,
                source TEXT,
                published_at TIMESTAMPTZ,
                url TEXT,
                bias TEXT,
                magnitude DOUBLE PRECISION,
                confidence DOUBLE PRECISION,
                severity TEXT,
                event_type_l1 TEXT,
                event_type_l2 TEXT,
                summary_cn TEXT,
                assets JSONB DEFAULT '[]'::jsonb,
                asset_clusters JSONB DEFAULT '[]'::jsonb,
                factor_tags JSONB DEFAULT '[]'::jsonb,
                impact_tags JSONB DEFAULT '[]'::jsonb,
                mapping_version TEXT,
                cross_market_impacts JSONB DEFAULT '[]'::jsonb,
                evidence_quotes JSONB DEFAULT '[]'::jsonb,
                final_status TEXT,
                interpret_status TEXT DEFAULT 'NEW',
                retry_count INTEGER DEFAULT 0,
                next_retry_at TIMESTAMPTZ DEFAULT NOW(),
                last_error TEXT,
                interpreted_at TIMESTAMPTZ,
                interpreter_version TEXT,
                content_fingerprint TEXT,
                fingerprint_algo TEXT,
                fingerprint_updated_at TIMESTAMPTZ,
                reinterpret_count INTEGER DEFAULT 0,
                last_reinterpret_reason TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS content_fingerprint TEXT",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS fingerprint_algo TEXT",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS fingerprint_updated_at TIMESTAMPTZ",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS reinterpret_count INTEGER DEFAULT 0",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS last_reinterpret_reason TEXT",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS asset_clusters JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS factor_tags JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS impact_tags JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS mapping_version TEXT",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS noise_flags JSONB DEFAULT '[]'::jsonb",
            "CREATE INDEX IF NOT EXISTS idx_news_interp_status_retry ON news_interpretations (interpret_status, next_retry_at)",
            "CREATE INDEX IF NOT EXISTS idx_news_interp_interpreted_at ON news_interpretations (interpreted_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_news_interp_severity_time ON news_interpretations (severity, interpreted_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_news_interp_final_status_time ON news_interpretations (final_status, interpreted_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_news_interp_assets_gin ON news_interpretations USING GIN (assets)",
            "CREATE INDEX IF NOT EXISTS idx_news_interp_asset_clusters_gin ON news_interpretations USING GIN (asset_clusters)",
            "CREATE INDEX IF NOT EXISTS idx_news_interp_factor_tags_gin ON news_interpretations USING GIN (factor_tags)"
        ]
        with self.engine.begin() as conn:
            for stmt in ddl_statements:
                conn.execute(text(stmt))
        self._schema_ready = True

    def _normalize_text_for_fingerprint(self, value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _compute_content_fingerprint(self, item: Dict[str, Any]) -> str:
        title = self._normalize_text_for_fingerprint(item.get("title"))
        summary = self._normalize_text_for_fingerprint(item.get("summary"))
        content = self._normalize_text_for_fingerprint(item.get("content"))
        raw = f"{title}|{summary}|{content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def queue_recent_news_for_interpretation(self, news_items: List[Dict]) -> int:
        self._ensure_interpretation_schema()
        upsert_sql = text("""
            INSERT INTO news_interpretations
            (news_id, title, source, published_at, url, interpret_status, next_retry_at, interpreter_version, content_fingerprint, fingerprint_algo, fingerprint_updated_at, updated_at)
            VALUES
            (:news_id, :title, :source, :published_at, :url, 'NEW', NOW(), :interpreter_version, :content_fingerprint, :fingerprint_algo, NOW(), NOW())
            ON CONFLICT (news_id) DO UPDATE SET
                title = EXCLUDED.title,
                source = EXCLUDED.source,
                published_at = EXCLUDED.published_at,
                url = EXCLUDED.url,
                content_fingerprint = EXCLUDED.content_fingerprint,
                fingerprint_algo = EXCLUDED.fingerprint_algo,
                fingerprint_updated_at = NOW(),
                interpret_status = CASE
                    WHEN news_interpretations.interpret_status = 'INTERPRETED'
                         AND COALESCE(news_interpretations.content_fingerprint, '') <> COALESCE(EXCLUDED.content_fingerprint, '')
                    THEN 'NEW'
                    ELSE news_interpretations.interpret_status
                END,
                retry_count = CASE
                    WHEN news_interpretations.interpret_status = 'INTERPRETED'
                         AND COALESCE(news_interpretations.content_fingerprint, '') <> COALESCE(EXCLUDED.content_fingerprint, '')
                    THEN 0
                    ELSE news_interpretations.retry_count
                END,
                next_retry_at = CASE
                    WHEN news_interpretations.interpret_status = 'INTERPRETED'
                         AND COALESCE(news_interpretations.content_fingerprint, '') <> COALESCE(EXCLUDED.content_fingerprint, '')
                    THEN NOW()
                    ELSE news_interpretations.next_retry_at
                END,
                last_error = CASE
                    WHEN news_interpretations.interpret_status = 'INTERPRETED'
                         AND COALESCE(news_interpretations.content_fingerprint, '') <> COALESCE(EXCLUDED.content_fingerprint, '')
                    THEN NULL
                    ELSE news_interpretations.last_error
                END,
                reinterpret_count = CASE
                    WHEN news_interpretations.interpret_status = 'INTERPRETED'
                         AND COALESCE(news_interpretations.content_fingerprint, '') <> COALESCE(EXCLUDED.content_fingerprint, '')
                    THEN COALESCE(news_interpretations.reinterpret_count, 0) + 1
                    ELSE news_interpretations.reinterpret_count
                END,
                last_reinterpret_reason = CASE
                    WHEN news_interpretations.interpret_status = 'INTERPRETED'
                         AND COALESCE(news_interpretations.content_fingerprint, '') <> COALESCE(EXCLUDED.content_fingerprint, '')
                    THEN 'fingerprint_changed'
                    ELSE news_interpretations.last_reinterpret_reason
                END,
                updated_at = NOW()
        """)
        inserted = 0
        with self.engine.begin() as conn:
            for item in news_items:
                if not item.get("id"):
                    continue
                content_fingerprint = self._compute_content_fingerprint(item)
                conn.execute(upsert_sql, {
                    "news_id": item["id"],
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "published_at": item.get("published_at"),
                    "url": item.get("url"),
                    "interpreter_version": self.interpreter_version,
                    "content_fingerprint": content_fingerprint,
                    "fingerprint_algo": "sha256:v1"
                })
                inserted += 1
        return inserted

    def claim_pending_interpretations(self, limit: int = 200) -> List[Dict]:
        self._ensure_interpretation_schema()
        claim_sql = text("""
            WITH cte AS (
                SELECT id
                FROM news_interpretations
                WHERE interpret_status IN ('NEW', 'RETRY_WAIT')
                  AND next_retry_at <= NOW()
                ORDER BY published_at DESC
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
            )
            UPDATE news_interpretations n
            SET interpret_status = 'INTERPRETING',
                updated_at = NOW()
            FROM cte
            WHERE n.id = cte.id
            RETURNING n.id, n.news_id, n.title, n.source, n.published_at, n.url
        """)
        with self.engine.begin() as conn:
            rows = conn.execute(claim_sql, {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]

    def _retry_backoff_seconds(self, retry_count: int) -> int:
        schedule = [30, 90, 240, 600, 1800]
        idx = max(0, min(retry_count - 1, len(schedule) - 1))
        return schedule[idx]

    def mark_interpretation_success(self, news_id: str, payload: Dict):
        self._ensure_interpretation_schema()
        sql = text("""
            UPDATE news_interpretations
            SET bias = :bias,
                magnitude = :magnitude,
                confidence = :confidence,
                severity = :severity,
                event_type_l1 = :event_type_l1,
                event_type_l2 = :event_type_l2,
                summary_cn = :summary_cn,
                assets = CAST(:assets AS JSONB),
                asset_clusters = CAST(:asset_clusters AS JSONB),
                factor_tags = CAST(:factor_tags AS JSONB),
                impact_tags = CAST(:impact_tags AS JSONB),
                mapping_version = :mapping_version,
                cross_market_impacts = CAST(:cross_market_impacts AS JSONB),
                evidence_quotes = CAST(:evidence_quotes AS JSONB),
                noise_flags = CAST(:noise_flags AS JSONB),
                final_status = :final_status,
                interpret_status = 'INTERPRETED',
                interpreted_at = NOW(),
                last_error = NULL,
                interpreter_version = :interpreter_version,
                updated_at = NOW()
            WHERE news_id = CAST(:news_id AS UUID)
        """)
        import json
        with self.engine.begin() as conn:
            conn.execute(sql, {
                "news_id": news_id,
                "bias": payload.get("bias"),
                "magnitude": payload.get("magnitude"),
                "confidence": payload.get("confidence"),
                "severity": payload.get("severity"),
                "event_type_l1": payload.get("event_type_l1"),
                "event_type_l2": payload.get("event_type_l2"),
                "summary_cn": payload.get("summary_cn"),
                "assets": json.dumps(payload.get("asset_mentions", []), ensure_ascii=False),
                "asset_clusters": json.dumps(payload.get("asset_clusters", []), ensure_ascii=False),
                "factor_tags": json.dumps(payload.get("factor_tags", []), ensure_ascii=False),
                "impact_tags": json.dumps(payload.get("impact_tags", []), ensure_ascii=False),
                "mapping_version": payload.get("mapping_version", self.taxonomy_version),
                "cross_market_impacts": json.dumps(payload.get("cross_market_impacts", []), ensure_ascii=False),
                "evidence_quotes": json.dumps(payload.get("evidence_quotes", []), ensure_ascii=False),
                "noise_flags": json.dumps(payload.get("noise_flags", []), ensure_ascii=False),
                "final_status": payload.get("final_status"),
                "interpreter_version": self.interpreter_version
            })

    def mark_interpretation_failure(self, news_id: str, error_message: str):
        self._ensure_interpretation_schema()
        fetch_sql = text("SELECT retry_count FROM news_interpretations WHERE news_id = CAST(:news_id AS UUID)")
        with self.engine.begin() as conn:
            row = conn.execute(fetch_sql, {"news_id": news_id}).first()
            retry_count = int(row[0] if row else 0) + 1
            if retry_count >= self.max_retry:
                conn.execute(text("""
                    UPDATE news_interpretations
                    SET retry_count = :retry_count,
                        interpret_status = 'DEAD_LETTER',
                        last_error = :last_error,
                        updated_at = NOW()
                    WHERE news_id = CAST(:news_id AS UUID)
                """), {
                    "news_id": news_id,
                    "retry_count": retry_count,
                    "last_error": (error_message or "")[:500]
                })
            else:
                backoff = self._retry_backoff_seconds(retry_count)
                conn.execute(text("""
                    UPDATE news_interpretations
                    SET retry_count = :retry_count,
                        interpret_status = 'RETRY_WAIT',
                        next_retry_at = NOW() + (:backoff || ' seconds')::interval,
                        last_error = :last_error,
                        updated_at = NOW()
                    WHERE news_id = CAST(:news_id AS UUID)
                """), {
                    "news_id": news_id,
                    "retry_count": retry_count,
                    "backoff": backoff,
                    "last_error": (error_message or "")[:500]
                })

    def load_interpreted_news(self, target_symbol: str, limit: int = 300, lookback_hours: int = 24, filter_by_symbol: bool = True) -> List[Dict]:
        self._ensure_interpretation_schema()
        base_asset = target_symbol.split("/")[0].upper()
        sql = text("""
            SELECT news_id, source, title, url, published_at, bias, magnitude, confidence, severity, final_status,
                   assets, asset_clusters, factor_tags, impact_tags, mapping_version,
                   cross_market_impacts, summary_cn, interpreted_at, noise_flags
            FROM news_interpretations
            WHERE interpret_status = 'INTERPRETED'
              AND interpreted_at >= NOW() - (:lookback_hours || ' hours')::interval
            ORDER BY interpreted_at DESC
            LIMIT :limit
        """)
        import json
        with self.engine.begin() as conn:
            rows = conn.execute(sql, {"lookback_hours": lookback_hours, "limit": limit}).mappings().all()
        results = []
        for row in rows:
            assets = row["assets"] if isinstance(row["assets"], list) else (json.loads(row["assets"]) if row["assets"] else [])
            asset_clusters = row["asset_clusters"] if isinstance(row["asset_clusters"], list) else (json.loads(row["asset_clusters"]) if row["asset_clusters"] else [])
            factor_tags = row["factor_tags"] if isinstance(row["factor_tags"], list) else (json.loads(row["factor_tags"]) if row["factor_tags"] else [])
            impact_tags = row["impact_tags"] if isinstance(row["impact_tags"], list) else (json.loads(row["impact_tags"]) if row["impact_tags"] else [])
            include = True
            if filter_by_symbol:
                include = self._matches_target_symbol(base_asset, assets, asset_clusters, impact_tags)
            if include:
                impacts = row["cross_market_impacts"] if isinstance(row["cross_market_impacts"], list) else (json.loads(row["cross_market_impacts"]) if row["cross_market_impacts"] else [])
                item = dict(row)
                item["assets"] = assets
                item["asset_clusters"] = asset_clusters
                item["factor_tags"] = factor_tags
                item["impact_tags"] = impact_tags
                item["cross_market_impacts"] = impacts
                item["noise_flags"] = row["noise_flags"] if isinstance(row["noise_flags"], list) else (json.loads(row["noise_flags"]) if row.get("noise_flags") else [])
                results.append(item)
        return results

    def _fingerprint(self, row: Dict[str, Any]) -> str:
        url = str(row.get("url") or "").strip().lower()
        if url:
            return f"url::{url}"
        title = " ".join(str(row.get("title") or "").strip().lower().split())
        source = str(row.get("source") or "").strip().lower()
        published = str(row.get("published_at") or "")[:16]
        return f"title::{title}|source::{source}|time::{published}"

    def _deduplicate_rows(self, rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for row in rows:
            fp = self._fingerprint(row)
            if fp in seen:
                continue
            seen.add(fp)
            deduped.append(row)
        return deduped, max(0, len(rows) - len(deduped))

    def aggregate_interpreted_news(self, target_symbol: str, fng: Dict, lookback_hours: int = 24) -> Dict:
        base_asset = target_symbol.split("/")[0].upper()
        rows_all = self.load_interpreted_news(target_symbol=target_symbol, limit=500, lookback_hours=max(1, lookback_hours))
        quality_rows = []
        for row in rows_all:
            conf = self._clamp(float(row.get("confidence") or 0.0), 0.0, 1.0)
            final_status = str(row.get("final_status") or "").lower()
            severity = str(row.get("severity") or "").lower()
            magnitude = float(row.get("magnitude") or 0.0)
            
            if conf < self.quality_confidence_floor:
                continue
            if self.exclude_insufficient_evidence and final_status == "insufficient_evidence":
                continue
            if self.exclude_low_severity and severity == "low":
                continue
            if magnitude < self.min_magnitude_floor:
                continue
            quality_rows.append(row)
        rows, dedup_removed_count = self._deduplicate_rows(quality_rows)
        raw_sample_count = len(rows_all)
        quality_sample_count = len(quality_rows)
        if not rows:
            return {
                "score": 0.0,
                "confidence": 0.2,
                "news_score": 0.0,
                "fng_score": self._clamp((float(fng.get("value", 50)) - 50.0) / 50.0, -1.0, 1.0),
                "drivers": [],
                "conflicts": ["low_sample"],
                "source_breakdown": {},
                "sample_count": 0,
                "raw_sample_count": raw_sample_count,
                "quality_sample_count": quality_sample_count,
                "dedup_removed_count": dedup_removed_count,
                "should_aggregate": False,
                "trigger_reason": "low_sample",
                "urgent_event": False,
                "trade_gate": "observe_only"
            }
        direction_map = {"bullish": 1.0, "bearish": -1.0, "mixed": 0.0, "neutral": 0.0, "unknown": 0.0}
        now = datetime.now(timezone.utc)
        weighted_sum = 0.0
        total_weight = 0.0
        source_breakdown: Dict[str, float] = {}
        positive_weight = 0.0
        negative_weight = 0.0
        drivers = []
        urgent_event = False
        for row in rows:
            source = str(row.get("source") or "unknown")
            source_weight = self.source_weights.get(source, 0.75)
            if source.startswith("CryptoPanic-"):
                source_weight = self.source_weights.get("CryptoPanic", 0.95)
            direction = direction_map.get(str(row.get("bias") or "unknown").lower(), 0.0)
            magnitude = self._clamp(float(row.get("magnitude") or 0.0), 0.0, 1.0)
            confidence = self._clamp(float(row.get("confidence") or 0.0), 0.0, 1.0)
            published_at = self._parse_published_at(str(row.get("published_at") or ""))
            age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
            recency = self._clamp(1.0 - age_hours / 24.0, 0.2, 1.0)
            relevance = self._relevance_for_symbol(row, base_asset)
            weight = source_weight * confidence * magnitude * recency * relevance
            contribution = direction * weight
            weighted_sum += contribution
            total_weight += weight
            source_breakdown[source] = source_breakdown.get(source, 0.0) + contribution
            if contribution > 0:
                positive_weight += contribution
            elif contribution < 0:
                negative_weight += abs(contribution)
            if magnitude >= 0.7 and confidence >= 0.65:
                drivers.append(str(row.get("summary_cn") or "")[:120])
            severity = str(row.get("severity") or "").lower()
            if severity in {"high", "critical"} and magnitude >= 0.7 and confidence >= self.major_event_confidence_floor:
                urgent_event = True
        news_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        fng_score = self._clamp((float(fng.get("value", 50)) - 50.0) / 50.0, -1.0, 1.0)
        score = self._clamp(news_score * 0.75 + fng_score * 0.25, -1.0, 1.0)
        sample_factor = self._clamp(len(rows) / 12.0, 0.2, 1.0)
        conflict_ratio = min(positive_weight, negative_weight) / max(positive_weight, negative_weight) if max(positive_weight, negative_weight) > 0 else 0.0
        confidence = self._clamp(0.35 + sample_factor * 0.45 - conflict_ratio * 0.25, 0.1, 0.95)
        conflicts = []
        if len(rows) < 3:
            conflicts.append("low_sample")
        if conflict_ratio > 0.6:
            conflicts.append("high_conflict")
        sample_count = len(rows)
        should_aggregate = sample_count >= 8 or urgent_event or sample_count >= 3
        trigger_reason = "threshold_8"
        if urgent_event:
            trigger_reason = "major_event"
        elif sample_count < 8 and sample_count >= 3:
            trigger_reason = "time_window"
        trade_gate = "normal"
        if urgent_event and (confidence < 0.75 or conflict_ratio > 0.5):
            trade_gate = "review_only"
        elif urgent_event:
            trade_gate = "risk_reduced"
        elif score < -0.6 or score > 0.6:
            trade_gate = "risk_reduced"
        return {
            "score": score,
            "confidence": confidence,
            "news_score": news_score,
            "fng_score": fng_score,
            "drivers": drivers[:5],
            "conflicts": conflicts,
            "source_breakdown": {k: round(v, 4) for k, v in source_breakdown.items()},
            "sample_count": sample_count,
            "raw_sample_count": raw_sample_count,
            "quality_sample_count": quality_sample_count,
            "dedup_removed_count": dedup_removed_count,
            "should_aggregate": should_aggregate,
            "trigger_reason": trigger_reason,
            "urgent_event": urgent_event,
            "trade_gate": trade_gate
        }

    def get_recent_interpretations(self, target_symbol: str = "BTC/USDT", limit: int = 20, scope: str = "symbol") -> List[Dict[str, Any]]:
        filter_by_symbol = str(scope).lower() != "all"
        rows = self.load_interpreted_news(target_symbol=target_symbol, limit=limit, lookback_hours=48, filter_by_symbol=filter_by_symbol)
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append({
                "news_id": str(row.get("news_id")),
                "source": row.get("source"),
                "published_at": str(row.get("published_at")),
                "bias": row.get("bias"),
                "magnitude": float(row.get("magnitude") or 0.0),
                "confidence": float(row.get("confidence") or 0.0),
                "severity": row.get("severity"),
                "final_status": row.get("final_status"),
                "summary_cn": row.get("summary_cn"),
                "assets": row.get("assets") or [],
                "asset_clusters": row.get("asset_clusters") or [],
                "factor_tags": row.get("factor_tags") or [],
                "impact_tags": row.get("impact_tags") or [],
                "mapping_version": row.get("mapping_version") or self.taxonomy_version,
                "cross_market_impacts": row.get("cross_market_impacts") or [],
                "noise_flags": row.get("noise_flags") or []
            })
        return result

    def get_interpretation_monitor(self, hours: int = 24) -> Dict[str, Any]:
        self._ensure_interpretation_schema()
        window_hours = max(1, min(hours, 168))
        with self.engine.begin() as conn:
            total = conn.execute(text("""
                SELECT COUNT(*)
                FROM news_interpretations
                WHERE interpret_status = 'INTERPRETED'
                  AND interpreted_at >= NOW() - (:hours || ' hours')::interval
            """), {"hours": window_hours}).scalar() or 0
            major = conn.execute(text("""
                SELECT COUNT(*)
                FROM news_interpretations
                WHERE interpret_status = 'INTERPRETED'
                  AND interpreted_at >= NOW() - (:hours || ' hours')::interval
                  AND severity IN ('high', 'critical')
                  AND magnitude >= 0.7
                  AND confidence >= :major_conf
                  AND COALESCE(final_status, 'unknown') <> 'insufficient_evidence'
            """), {"hours": window_hours, "major_conf": self.major_event_confidence_floor}).scalar() or 0
            quality_total = conn.execute(text("""
                SELECT COUNT(*)
                FROM news_interpretations
                WHERE interpret_status = 'INTERPRETED'
                  AND interpreted_at >= NOW() - (:hours || ' hours')::interval
                  AND confidence >= :quality_conf
                  AND COALESCE(final_status, 'unknown') <> 'insufficient_evidence'
            """), {"hours": window_hours, "quality_conf": self.quality_confidence_floor}).scalar() or 0
            avg_conf = conn.execute(text("""
                SELECT AVG(confidence)
                FROM news_interpretations
                WHERE interpret_status = 'INTERPRETED'
                  AND interpreted_at >= NOW() - (:hours || ' hours')::interval
            """), {"hours": window_hours}).scalar()
            severity_rows = conn.execute(text("""
                SELECT COALESCE(severity, 'unknown') AS severity, COUNT(*) AS cnt
                FROM news_interpretations
                WHERE interpret_status = 'INTERPRETED'
                  AND interpreted_at >= NOW() - (:hours || ' hours')::interval
                GROUP BY COALESCE(severity, 'unknown')
            """), {"hours": window_hours}).mappings().all()
            status_rows = conn.execute(text("""
                SELECT COALESCE(final_status, 'unknown') AS final_status, COUNT(*) AS cnt
                FROM news_interpretations
                WHERE interpret_status = 'INTERPRETED'
                  AND interpreted_at >= NOW() - (:hours || ' hours')::interval
                GROUP BY COALESCE(final_status, 'unknown')
            """), {"hours": window_hours}).mappings().all()
            queue_rows = conn.execute(text("""
                SELECT interpret_status, COUNT(*) AS cnt
                FROM news_interpretations
                GROUP BY interpret_status
            """)).mappings().all()
            dedup_rows = conn.execute(text("""
                SELECT title, source, url, published_at
                FROM news_interpretations
                WHERE interpret_status = 'INTERPRETED'
                  AND interpreted_at >= NOW() - (:hours || ' hours')::interval
                  AND confidence >= :quality_conf
                  AND COALESCE(final_status, 'unknown') <> 'insufficient_evidence'
                ORDER BY interpreted_at DESC
                LIMIT 5000
            """), {"hours": window_hours, "quality_conf": self.quality_confidence_floor}).mappings().all()
        dedup_list = [dict(r) for r in dedup_rows]
        _, dedup_removed = self._deduplicate_rows(dedup_list)
        return {
            "window_hours": window_hours,
            "total_interpreted": int(total),
            "quality_interpreted": int(quality_total),
            "major_event_count": int(major),
            "avg_confidence": float(avg_conf) if avg_conf is not None else 0.0,
            "dedup_removed_count": int(dedup_removed),
            "major_event_confidence_floor": self.major_event_confidence_floor,
            "quality_confidence_floor": self.quality_confidence_floor,
            "severity_distribution": {str(r["severity"]): int(r["cnt"]) for r in severity_rows},
            "final_status_distribution": {str(r["final_status"]): int(r["cnt"]) for r in status_rows},
            "queue_status_distribution": {str(r["interpret_status"]): int(r["cnt"]) for r in queue_rows}
        }

    def _parse_published_at(self, value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _infer_symbol_clusters(self, base_asset: str) -> List[str]:
        symbol = str(base_asset or "").upper()
        if symbol in {"BTC", "ETH"}:
            return ["CRYPTO_MAJOR", "CRYPTO_L1"]
        if symbol in {"USDT", "USDC", "DAI", "FDUSD", "USDE", "TUSD"}:
            return ["STABLECOIN"]
        if symbol in {"UNI", "AAVE", "MKR", "CRV", "LDO", "SUSHI", "COMP"}:
            return ["CRYPTO_DEFI"]
        return ["CRYPTO_L1"]

    def _normalize_cluster(self, value: Any) -> str:
        cluster = str(value or "").strip().upper()
        return cluster if cluster in self.cluster_defaults else ""

    def _extract_clusters_from_impact_tags(self, impact_tags: List[Any]) -> List[str]:
        clusters: List[str] = []
        for tag in impact_tags:
            if not isinstance(tag, dict):
                continue
            cluster = self._normalize_cluster(tag.get("asset_cluster"))
            if cluster:
                clusters.append(cluster)
        return clusters

    def _matches_target_symbol(
        self,
        base_asset: str,
        assets: List[Any],
        asset_clusters: List[Any],
        impact_tags: List[Any]
    ) -> bool:
        target_clusters = set(self._infer_symbol_clusters(base_asset))
        normalized_clusters = {
            self._normalize_cluster(c) for c in asset_clusters if self._normalize_cluster(c)
        }
        impact_clusters = set(self._extract_clusters_from_impact_tags(impact_tags))
        if normalized_clusters & target_clusters:
            return True
        if impact_clusters & target_clusters:
            return True
        for asset in assets:
            sym = ""
            if isinstance(asset, str):
                sym = asset.upper()
            elif isinstance(asset, dict):
                sym = str(asset.get("symbol", "")).upper()
            
            if sym == base_asset:
                return True
                
            if sym:
                sym_clusters = set(self._infer_symbol_clusters(sym))
                if sym_clusters & target_clusters:
                    return True

        return len(assets) == 0 and len(normalized_clusters) == 0 and len(impact_clusters) == 0

    def _relevance_for_symbol(self, row: Dict[str, Any], base_asset: str) -> float:
        target_clusters = set(self._infer_symbol_clusters(base_asset))
        row_clusters = {
            self._normalize_cluster(c) for c in (row.get("asset_clusters") or []) if self._normalize_cluster(c)
        }
        impact_clusters = set(self._extract_clusters_from_impact_tags(row.get("impact_tags") or []))
        if row_clusters & target_clusters:
            return float(self.relevance_weights.get("cluster_match", 1.0))
        if impact_clusters & target_clusters:
            return float(self.relevance_weights.get("impact_cluster_match", 0.9))
        assets = row.get("assets") or []
        for asset in assets:
            sym = ""
            if isinstance(asset, str):
                sym = asset.upper()
            elif isinstance(asset, dict):
                sym = str(asset.get("symbol", "")).upper()
                
            if sym == base_asset:
                return float(self.relevance_weights.get("symbol_match", 0.95))
                
            if sym:
                sym_clusters = set(self._infer_symbol_clusters(sym))
                if sym_clusters & target_clusters:
                    return float(self.relevance_weights.get("symbol_cluster_match", 0.85))

        if not row_clusters and not impact_clusters and not assets:
            return float(self.relevance_weights.get("unknown_general", 0.6))
        if "MACRO" in row_clusters:
            return float(self.relevance_weights.get("macro_only", 0.75))
        return float(self.relevance_weights.get("other_related", 0.4))

    def build_rule_packet(self, news: List[Dict], fng: Dict) -> Dict:
        now = datetime.now(timezone.utc)
        source_breakdown: Dict[str, float] = {}
        weighted_total = 0.0
        total_weight = 0.0
        for item in news:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "unknown")
            title = str(item.get("title") or "")
            summary = str(item.get("summary") or "")
            text = f"{title} {summary}".lower()
            bulls = sum(1 for kw in self.bullish_keywords if kw in text)
            bears = sum(1 for kw in self.bearish_keywords if kw in text)
            raw = 0.0
            if bulls or bears:
                raw = (bulls - bears) / float(bulls + bears)
            published_at = self._parse_published_at(item.get("published_at"))
            age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
            recency = self._clamp(1.0 - age_hours / 24.0, 0.2, 1.0)
            source_weight = self.source_weights.get(source, 0.75)
            contribution = raw * source_weight * recency
            weighted_total += contribution
            total_weight += source_weight * recency
            source_breakdown[source] = source_breakdown.get(source, 0.0) + contribution
        news_score = weighted_total / total_weight if total_weight > 0 else 0.0
        fng_value = float(fng.get("value", 50))
        fng_score = self._clamp((fng_value - 50.0) / 50.0, -1.0, 1.0)
        rule_score = self._clamp(news_score * 0.75 + fng_score * 0.25, -1.0, 1.0)
        source_count = len({k for k, v in source_breakdown.items() if abs(v) > 0.0001})
        confidence = self._clamp(0.35 + min(0.35, len(news) * 0.03) + min(0.2, source_count * 0.05), 0.1, 0.95)
        return {
            "rule_score": rule_score,
            "confidence": confidence,
            "news_score": news_score,
            "fng_score": fng_score,
            "source_breakdown": {k: round(v, 4) for k, v in source_breakdown.items()}
        }

sentiment_service = SentimentService()
