from sqlalchemy.orm import Session
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
        return snapshot
