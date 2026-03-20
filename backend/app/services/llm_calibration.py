import json
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.session import engine_user, engine_market


class LLMCalibrationService:
    def __init__(self):
        self.source_weights = {
            "TechFlow-OnchainWhale": 1.25,
            "TechFlow-Newsletter": 1.0,
            "CryptoPanic": 0.95,
            "CoinDesk": 0.9,
            "Cointelegraph": 0.9,
        }
        self.allowed_clusters = {
            "CRYPTO_MAJOR",
            "CRYPTO_L1",
            "CRYPTO_DEFI",
            "STABLECOIN",
            "EQUITY_CRYPTO_PROXY",
            "MACRO",
        }
        self._schema_ready = False

    def _default_tuning_params(self) -> Dict[str, Any]:
        return {
            "quality_confidence_floor": 0.35,
            "exclude_insufficient_evidence": True,
            "exclude_low_severity": True,
            "min_magnitude": 0.35,
            "major_event_confidence_floor": 0.55,
            "relevance_weights": {
                "cluster_match": 1.0,
                "impact_cluster_match": 0.9,
                "symbol_match": 0.95,
                "macro_only": 0.75,
                "unknown_general": 0.6,
                "other_related": 0.4,
            },
        }

    def _normalize_tuning_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged = self._default_tuning_params()
        if isinstance(params, dict):
            merged.update({k: v for k, v in params.items() if k in merged})
            if isinstance(params.get("relevance_weights"), dict):
                weights = dict(merged["relevance_weights"])
                for k in weights.keys():
                    if k in params["relevance_weights"]:
                        try:
                            weights[k] = float(params["relevance_weights"][k])
                        except Exception:
                            pass
                merged["relevance_weights"] = weights
        merged["quality_confidence_floor"] = max(0.0, min(0.95, float(merged["quality_confidence_floor"])))
        merged["min_magnitude"] = max(0.0, min(1.0, float(merged["min_magnitude"])))
        merged["major_event_confidence_floor"] = max(0.0, min(1.0, float(merged["major_event_confidence_floor"])))
        merged["exclude_insufficient_evidence"] = bool(merged["exclude_insufficient_evidence"])
        merged["exclude_low_severity"] = bool(merged["exclude_low_severity"])
        for key, value in list(merged["relevance_weights"].items()):
            merged["relevance_weights"][key] = max(0.0, min(1.2, float(value)))
        return merged

    def build_daily_candidate_params(self, baseline: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        base = self._normalize_tuning_params(baseline)
        q = base["quality_confidence_floor"]
        m = base["min_magnitude"]
        r = base["relevance_weights"]["other_related"]
        return [
            {**base, "label": "baseline"},
            {**base, "label": "quality_up", "quality_confidence_floor": round(min(0.95, q + 0.03), 2)},
            {**base, "label": "quality_down", "quality_confidence_floor": round(max(0.0, q - 0.03), 2)},
            {**base, "label": "magnitude_up", "min_magnitude": round(min(1.0, m + 0.05), 2)},
            {**base, "label": "magnitude_down", "min_magnitude": round(max(0.0, m - 0.05), 2)},
            {
                **base,
                "label": "related_relaxed",
                "relevance_weights": {**base["relevance_weights"], "other_related": round(min(1.2, r + 0.1), 2)},
            },
            {
                **base,
                "label": "related_strict",
                "relevance_weights": {**base["relevance_weights"], "other_related": round(max(0.0, r - 0.1), 2)},
            },
        ]

    def _ensure_schema(self):
        if self._schema_ready:
            return
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS llm_score_calibration_reports (
                id BIGSERIAL PRIMARY KEY,
                run_date DATE NOT NULL,
                symbol TEXT NOT NULL,
                window_days INTEGER NOT NULL,
                methodology JSONB NOT NULL,
                execution_process JSONB NOT NULL,
                metrics JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(run_date, symbol)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_llm_calibration_created_at ON llm_score_calibration_reports (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_llm_calibration_symbol_date ON llm_score_calibration_reports (symbol, run_date DESC)",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS asset_clusters JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS factor_tags JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS impact_tags JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE news_interpretations ADD COLUMN IF NOT EXISTS mapping_version TEXT",
        ]
        with engine_user.begin() as conn:
            for stmt in ddl:
                conn.execute(text(stmt))
        self._schema_ready = True

    def _parse_json(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return []

    def _to_dt(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

    def _normalize_cluster(self, value: Any) -> str:
        cluster = str(value or "").strip().upper()
        return cluster if cluster in self.allowed_clusters else ""

    def _infer_symbol_clusters(self, symbol: str) -> set[str]:
        base = str(symbol or "").split("/")[0].upper()
        if base in {"BTC", "ETH"}:
            return {"CRYPTO_MAJOR", "CRYPTO_L1"}
        if base in {"USDT", "USDC", "DAI", "FDUSD", "USDE", "TUSD"}:
            return {"STABLECOIN"}
        if base in {"UNI", "AAVE", "MKR", "CRV", "LDO", "SUSHI", "COMP"}:
            return {"CRYPTO_DEFI"}
        return {"CRYPTO_L1"}

    def _extract_impact_clusters(self, impact_tags: List[Any]) -> set[str]:
        clusters = set()
        for tag in impact_tags:
            if not isinstance(tag, dict):
                continue
            cluster = self._normalize_cluster(tag.get("asset_cluster"))
            if cluster:
                clusters.add(cluster)
        return clusters

    def _old_include(self, row: Dict[str, Any], base_asset: str) -> bool:
        assets = self._parse_json(row.get("assets"))
        if not assets:
            return True
        for asset in assets:
            if isinstance(asset, str) and asset.upper() == base_asset:
                return True
            if isinstance(asset, dict) and str(asset.get("symbol", "")).upper() == base_asset:
                return True
        return False

    def _new_include(self, row: Dict[str, Any], base_asset: str, target_clusters: set[str]) -> bool:
        assets = self._parse_json(row.get("assets"))
        row_clusters = {
            self._normalize_cluster(c)
            for c in self._parse_json(row.get("asset_clusters"))
            if self._normalize_cluster(c)
        }
        impact_clusters = self._extract_impact_clusters(self._parse_json(row.get("impact_tags")))
        if row_clusters & target_clusters:
            return True
        if impact_clusters & target_clusters:
            return True
        for asset in assets:
            if isinstance(asset, str) and asset.upper() == base_asset:
                return True
            if isinstance(asset, dict) and str(asset.get("symbol", "")).upper() == base_asset:
                return True
        return len(assets) == 0 and len(row_clusters) == 0 and len(impact_clusters) == 0

    def _new_relevance(self, row: Dict[str, Any], base_asset: str, target_clusters: set[str], relevance_weights: Dict[str, Any]) -> float:
        assets = self._parse_json(row.get("assets"))
        row_clusters = {
            self._normalize_cluster(c)
            for c in self._parse_json(row.get("asset_clusters"))
            if self._normalize_cluster(c)
        }
        impact_clusters = self._extract_impact_clusters(self._parse_json(row.get("impact_tags")))
        if row_clusters & target_clusters:
            return float(relevance_weights.get("cluster_match", 1.0))
        if impact_clusters & target_clusters:
            return float(relevance_weights.get("impact_cluster_match", 0.9))
        for asset in assets:
            if isinstance(asset, str) and asset.upper() == base_asset:
                return float(relevance_weights.get("symbol_match", 0.95))
            if isinstance(asset, dict) and str(asset.get("symbol", "")).upper() == base_asset:
                return float(relevance_weights.get("symbol_match", 0.95))
        if not row_clusters and not impact_clusters and not assets:
            return float(relevance_weights.get("unknown_general", 0.6))
        if "MACRO" in row_clusters:
            return float(relevance_weights.get("macro_only", 0.75))
        return float(relevance_weights.get("other_related", 0.4))

    def _fetch_rows(self, window_days: int) -> List[Dict[str, Any]]:
        sql = text(
            """
            SELECT interpreted_at, published_at, source, bias, magnitude, confidence, final_status,
                   severity, assets, asset_clusters, impact_tags
            FROM news_interpretations
            WHERE interpret_status='INTERPRETED'
              AND interpreted_at >= NOW() - (:days || ' days')::interval
            ORDER BY interpreted_at ASC
            """
        )
        with engine_user.begin() as conn:
            rows = conn.execute(sql, {"days": int(window_days)}).mappings().all()
        return [dict(r) for r in rows]

    def _fetch_eth_prices(self, window_days: int, symbol: str) -> tuple[List[float], List[float]]:
        sql = text(
            """
            SELECT time, close
            FROM market_klines
            WHERE symbol=:symbol
              AND interval='1m'
              AND time >= NOW() - (:days || ' days')::interval
            ORDER BY time ASC
            """
        )
        with engine_market.begin() as conn:
            rows = conn.execute(sql, {"days": int(window_days) + 1, "symbol": symbol}).mappings().all()
        ts_list: List[float] = []
        prices: List[float] = []
        for row in rows:
            ts_list.append(self._to_dt(row["time"]).timestamp())
            prices.append(float(row["close"]))
        return ts_list, prices

    def _price_at_or_before(self, ts_list: List[float], prices: List[float], target_ts: float) -> Optional[float]:
        idx = bisect_right(ts_list, target_ts) - 1
        if idx < 0:
            return None
        return prices[idx]

    def _future_return(self, ts_list: List[float], prices: List[float], start_ts: float, horizon_sec: int) -> Optional[float]:
        p0 = self._price_at_or_before(ts_list, prices, start_ts)
        p1 = self._price_at_or_before(ts_list, prices, start_ts + horizon_sec)
        if p0 is None or p1 is None or p0 == 0:
            return None
        return (p1 - p0) / p0

    def _compute_metrics(
        self,
        rows: List[Dict[str, Any]],
        mode: str,
        symbol: str,
        ts_list: List[float],
        prices: List[float],
        tuning_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        base_asset = symbol.split("/")[0].upper()
        target_clusters = self._infer_symbol_clusters(symbol)
        direction_map = {"bullish": 1, "bearish": -1, "mixed": 0, "neutral": 0, "unknown": 0}
        selected: List[Dict[str, Any]] = []
        for row in rows:
            conf = max(0.0, min(1.0, float(row.get("confidence") or 0.0)))
            mag = max(0.0, min(1.0, float(row.get("magnitude") or 0.0)))
            severity = str(row.get("severity") or "").lower()
            final_status = str(row.get("final_status") or "unknown").lower()
            if conf < float(tuning_params["quality_confidence_floor"]):
                continue
            if bool(tuning_params["exclude_insufficient_evidence"]) and final_status == "insufficient_evidence":
                continue
            if bool(tuning_params["exclude_low_severity"]) and severity == "low":
                continue
            if mag < float(tuning_params["min_magnitude"]):
                continue
            include = self._old_include(row, base_asset) if mode == "before" else self._new_include(row, base_asset, target_clusters)
            if not include:
                continue
            item = dict(row)
            item["_relevance"] = 1.0 if mode == "before" else self._new_relevance(
                row, base_asset, target_clusters, tuning_params.get("relevance_weights", {})
            )
            selected.append(item)

        hit_1h = {"valid": 0, "hits": 0}
        hit_4h = {"valid": 0, "hits": 0}
        by_hour = defaultdict(list)
        total_pos = 0.0
        total_neg = 0.0

        for row in selected:
            direction = direction_map.get(str(row.get("bias") or "").lower(), 0)
            source = str(row.get("source") or "unknown")
            source_weight = self.source_weights.get(source, 0.75)
            if source.startswith("CryptoPanic-"):
                source_weight = self.source_weights.get("CryptoPanic", 0.95)
            conf = max(0.0, min(1.0, float(row.get("confidence") or 0.0)))
            mag = max(0.0, min(1.0, float(row.get("magnitude") or 0.0)))
            contribution = direction * source_weight * conf * mag * float(row["_relevance"])
            if contribution > 0:
                total_pos += contribution
            elif contribution < 0:
                total_neg += abs(contribution)

            event_dt = self._to_dt(row.get("published_at") or row.get("interpreted_at"))
            hour_key = event_dt.replace(minute=0, second=0, microsecond=0)
            by_hour[hour_key].append(contribution)
            event_ts = event_dt.timestamp()

            if direction != 0:
                r1 = self._future_return(ts_list, prices, event_ts, 3600)
                r4 = self._future_return(ts_list, prices, event_ts, 4 * 3600)
                if r1 is not None and r1 != 0:
                    hit_1h["valid"] += 1
                    if (r1 > 0 and direction > 0) or (r1 < 0 and direction < 0):
                        hit_1h["hits"] += 1
                if r4 is not None and r4 != 0:
                    hit_4h["valid"] += 1
                    if (r4 > 0 and direction > 0) or (r4 < 0 and direction < 0):
                        hit_4h["hits"] += 1

        conflict_hours = 0
        for values in by_hour.values():
            pos = sum(v for v in values if v > 0)
            neg = sum(-v for v in values if v < 0)
            if max(pos, neg) > 0:
                ratio = min(pos, neg) / max(pos, neg)
                if ratio > 0.6:
                    conflict_hours += 1
        overall_conflict_ratio = (min(total_pos, total_neg) / max(total_pos, total_neg)) if max(total_pos, total_neg) > 0 else 0.0
        total_hours = max(1, len(by_hour))

        conf_dist = {"0-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
        for row in selected:
            c = max(0.0, min(1.0, float(row.get("confidence") or 0.0)))
            if c < 0.4:
                conf_dist["0-0.4"] += 1
            elif c < 0.6:
                conf_dist["0.4-0.6"] += 1
            elif c < 0.8:
                conf_dist["0.6-0.8"] += 1
            else:
                conf_dist["0.8-1.0"] += 1

        return {
            "selected_samples": len(selected),
            "hit_rate_1h": round(hit_1h["hits"] / hit_1h["valid"], 4) if hit_1h["valid"] else None,
            "hit_valid_n_1h": hit_1h["valid"],
            "hit_rate_4h": round(hit_4h["hits"] / hit_4h["valid"], 4) if hit_4h["valid"] else None,
            "hit_valid_n_4h": hit_4h["valid"],
            "overall_conflict_ratio": round(overall_conflict_ratio, 4),
            "hour_conflict_rate": round(conflict_hours / total_hours, 4),
            "confidence_distribution": conf_dist,
        }

    def run_daily_calibration(self, symbol: str = "ETH/USDT", window_days: int = 14, tuning_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_schema()
        normalized_params = self._normalize_tuning_params(tuning_params)
        rows = self._fetch_rows(window_days=window_days)
        ts_list, prices = self._fetch_eth_prices(window_days=window_days, symbol=symbol)
        if not ts_list or not prices:
            raise ValueError("No market kline data for calibration window")

        before_metrics = self._compute_metrics(
            rows, mode="before", symbol=symbol, ts_list=ts_list, prices=prices, tuning_params=self._default_tuning_params()
        )
        after_metrics = self._compute_metrics(
            rows, mode="after", symbol=symbol, ts_list=ts_list, prices=prices, tuning_params=normalized_params
        )
        methodology = [
            "弱监督标签: 用新闻发布时间后1h/4h收益方向作为方向标签。",
            "Walk-forward思想: 每日滚动重复校准，不在同一窗口内回看拟合。",
            "多目标优化: 同时关注命中率、冲突率、置信度分布稳定性。",
            "上线约束: 新方案命中率不显著劣化且冲突率受控。"
        ]
        execution_process = [
            f"Step1: 读取近{window_days}天news_interpretations高质量样本。",
            f"Step2: 读取{symbol} 1m行情并构造1h/4h弱标签。",
            "Step3: 按旧逻辑与新逻辑并行回放计算指标。",
            "Step4: 输出对比结果并保存为每日校准报告。"
        ]
        metrics = {
            "symbol": symbol,
            "window_days": window_days,
            "parameters": normalized_params,
            "before": before_metrics,
            "after": after_metrics,
            "delta": {
                "hit_rate_1h": None if before_metrics["hit_rate_1h"] is None or after_metrics["hit_rate_1h"] is None else round(after_metrics["hit_rate_1h"] - before_metrics["hit_rate_1h"], 4),
                "hit_rate_4h": None if before_metrics["hit_rate_4h"] is None or after_metrics["hit_rate_4h"] is None else round(after_metrics["hit_rate_4h"] - before_metrics["hit_rate_4h"], 4),
                "overall_conflict_ratio": round(after_metrics["overall_conflict_ratio"] - before_metrics["overall_conflict_ratio"], 4),
                "hour_conflict_rate": round(after_metrics["hour_conflict_rate"] - before_metrics["hour_conflict_rate"], 4),
            },
            "decision": {
                "passed": (
                    (after_metrics["hit_rate_4h"] is not None and before_metrics["hit_rate_4h"] is not None and after_metrics["hit_rate_4h"] >= before_metrics["hit_rate_4h"])
                    and after_metrics["overall_conflict_ratio"] <= before_metrics["overall_conflict_ratio"] + 0.03
                    and after_metrics["selected_samples"] >= int(max(1, before_metrics["selected_samples"] * 0.7))
                ),
                "rules": [
                    "4H命中率不低于基线",
                    "总体冲突率不劣化超过0.03",
                    "样本数不低于基线的70%"
                ]
            }
        }
        run_date = datetime.now(timezone.utc).date().isoformat()
        payload = {
            "run_date": run_date,
            "symbol": symbol,
            "window_days": int(window_days),
            "methodology": methodology,
            "execution_process": execution_process,
            "metrics": metrics,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        upsert_sql = text(
            """
            INSERT INTO llm_score_calibration_reports (run_date, symbol, window_days, methodology, execution_process, metrics)
            VALUES (CAST(:run_date AS DATE), :symbol, :window_days, CAST(:methodology AS JSONB), CAST(:execution_process AS JSONB), CAST(:metrics AS JSONB))
            ON CONFLICT (run_date, symbol) DO UPDATE SET
                window_days = EXCLUDED.window_days,
                methodology = EXCLUDED.methodology,
                execution_process = EXCLUDED.execution_process,
                metrics = EXCLUDED.metrics,
                created_at = NOW()
            """
        )
        with engine_user.begin() as conn:
            conn.execute(
                upsert_sql,
                {
                    "run_date": run_date,
                    "symbol": symbol,
                    "window_days": int(window_days),
                    "methodology": json.dumps(methodology, ensure_ascii=False),
                    "execution_process": json.dumps(execution_process, ensure_ascii=False),
                    "metrics": json.dumps(metrics, ensure_ascii=False),
                },
            )
        return payload

    def get_latest_report(self, symbol: str = "ETH/USDT") -> Optional[Dict[str, Any]]:
        self._ensure_schema()
        sql = text(
            """
            SELECT run_date, symbol, window_days, methodology, execution_process, metrics, created_at
            FROM llm_score_calibration_reports
            WHERE symbol=:symbol
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        with engine_user.begin() as conn:
            row = conn.execute(sql, {"symbol": symbol}).mappings().first()
        if not row:
            return None
        return {
            "run_date": str(row["run_date"]),
            "symbol": row["symbol"],
            "window_days": int(row["window_days"]),
            "methodology": self._parse_json(row["methodology"]),
            "execution_process": self._parse_json(row["execution_process"]),
            "metrics": row["metrics"] if isinstance(row["metrics"], dict) else json.loads(row["metrics"]),
            "created_at": self._to_dt(row["created_at"]).isoformat(),
        }

    def get_history(self, symbol: str = "ETH/USDT", limit: int = 30) -> List[Dict[str, Any]]:
        self._ensure_schema()
        sql = text(
            """
            SELECT run_date, symbol, window_days, metrics, created_at
            FROM llm_score_calibration_reports
            WHERE symbol=:symbol
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        with engine_user.begin() as conn:
            rows = conn.execute(sql, {"symbol": symbol, "limit": max(1, min(limit, 180))}).mappings().all()
        result: List[Dict[str, Any]] = []
        for row in rows:
            metrics = row["metrics"] if isinstance(row["metrics"], dict) else json.loads(row["metrics"])
            result.append(
                {
                    "run_date": str(row["run_date"]),
                    "created_at": self._to_dt(row["created_at"]).isoformat(),
                    "symbol": row["symbol"],
                    "window_days": int(row["window_days"]),
                    "before": metrics.get("before", {}),
                    "after": metrics.get("after", {}),
                    "delta": metrics.get("delta", {}),
                }
            )
        return result


llm_calibration_service = LLMCalibrationService()
