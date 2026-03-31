from sqlalchemy.orm import Session
from sqlalchemy import text
from shared.models.onchain import OnChainMetric

class OnChainDataService:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_snapshot(self, symbol: str) -> dict:
        metrics = self.db.query(OnChainMetric).filter(OnChainMetric.symbol == symbol).all()
        snapshot = {}
        for m in metrics:
            # Simple aggregation: latest per metric name
            if m.metric_name not in snapshot or m.timestamp > snapshot[m.metric_name]['timestamp']:
                snapshot[m.metric_name] = {
                    "value": m.value,
                    "unit": m.unit,
                    "timestamp": m.timestamp
                }
        snapshot["WALLET_SUMMARY"] = self.get_wallet_summary(symbol)
        return snapshot

    def get_wallet_events(self, symbol: str, hours: int = 24, limit: int = 50, min_usd: float = 0.0) -> list[dict]:
        base_symbol = symbol.split("/")[0].upper()
        query = text(
            """
            SELECT event_uid, source, source_news_url, title, summary, published_at, chain, tx_hash,
                   wallet_address, counterparty_address, direction, asset_symbol, amount, amount_usd
            FROM onchain_wallet_events
            WHERE published_at >= NOW() - (:hours || ' hours')::interval
              AND COALESCE(amount_usd, 0) >= :min_usd
              AND (
                  asset_symbol = :base_symbol
                  OR title ILIKE :base_like
                  OR summary ILIKE :base_like
              )
            ORDER BY published_at DESC
            LIMIT :limit
            """
        )
        try:
            rows = self.db.execute(
                query,
                {
                    "hours": int(max(1, hours)),
                    "min_usd": float(max(0.0, min_usd)),
                    "base_symbol": base_symbol,
                    "base_like": f"%{base_symbol}%",
                    "limit": int(max(1, min(500, limit))),
                },
            ).mappings().all()
        except Exception:
            return []
        return [dict(r) for r in rows]

    def get_wallet_summary(self, symbol: str, hours: int = 24) -> dict:
        events = self.get_wallet_events(symbol=symbol, hours=hours, limit=500, min_usd=0.0)
        if not events:
            return {
                "symbol": symbol,
                "window_hours": hours,
                "event_count": 0,
                "large_event_count": 0,
                "total_amount_usd": 0.0,
                "to_exchange_count": 0,
                "from_exchange_count": 0,
                "transfer_count": 0,
                "net_exchange_pressure": 0,
                "trade_gate": "normal",
                "trigger_reason": None,
                "latest_published_at": None,
                "top_events": [],
            }
        to_exchange_count = 0
        from_exchange_count = 0
        transfer_count = 0
        total_amount_usd = 0.0
        large_event_count = 0
        for event in events:
            direction = str(event.get("direction") or "")
            if direction == "to_exchange":
                to_exchange_count += 1
            elif direction == "from_exchange":
                from_exchange_count += 1
            else:
                transfer_count += 1
            usd = float(event.get("amount_usd") or 0.0)
            total_amount_usd += usd
            if usd >= 1_000_000:
                large_event_count += 1
        net_exchange_pressure = to_exchange_count - from_exchange_count
        trade_gate = "normal"
        trigger_reason = None
        if large_event_count >= 3 and net_exchange_pressure >= 2:
            trade_gate = "review_only"
            trigger_reason = "whale_to_exchange_concentration"
        elif large_event_count >= 2 and net_exchange_pressure >= 1:
            trade_gate = "risk_reduced"
            trigger_reason = "whale_to_exchange_bias"
        elif large_event_count >= 4:
            trade_gate = "risk_reduced"
            trigger_reason = "frequent_large_transfers"
        return {
            "symbol": symbol,
            "window_hours": hours,
            "event_count": len(events),
            "large_event_count": large_event_count,
            "total_amount_usd": round(total_amount_usd, 2),
            "to_exchange_count": to_exchange_count,
            "from_exchange_count": from_exchange_count,
            "transfer_count": transfer_count,
            "net_exchange_pressure": net_exchange_pressure,
            "trade_gate": trade_gate,
            "trigger_reason": trigger_reason,
            "latest_published_at": events[0].get("published_at"),
            "top_events": events[:5],
        }
