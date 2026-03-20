from sqlalchemy import Column, String, DateTime, Float, Index
from shared.db.base import Base
from datetime import datetime

class MacroMetric(Base):
    __tablename__ = "macro_metrics"

    id = Column(String, primary_key=True)
    metric_name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_macro_metric_time', 'metric_name', 'timestamp'),
    )
