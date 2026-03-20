from sqlalchemy.orm import Session
from shared.models.macro import MacroMetric
import logging

logger = logging.getLogger(__name__)

class MacroDataService:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_snapshot(self) -> dict:
        """
        Get the latest metrics from DB.
        Returns a dictionary keyed by metric name.
        """
        metrics = self.db.query(MacroMetric).all()
        snapshot = {}
        for m in metrics:
            if m.metric_name not in snapshot or m.timestamp > snapshot[m.metric_name]['timestamp']:
                snapshot[m.metric_name] = {
                    "price": m.value,
                    "unit": m.unit,
                    "timestamp": m.timestamp,
                    "category": m.category
                }
        return snapshot
