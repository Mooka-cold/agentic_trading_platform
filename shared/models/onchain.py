from sqlalchemy import Column, String, DateTime, Float, Index
from shared.db.base import Base
from datetime import datetime

class OnChainMetric(Base):
    __tablename__ = "onchain_metrics"

    id = Column(String, primary_key=True) # e.g. BTC_OI, BTC_LS_RATIO
    symbol = Column(String, nullable=False) # BTC, ETH
    metric_name = Column(String, nullable=False) # OI, LS_RATIO, INFLOW, FUNDING
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True) # USD, Ratio, BTC
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_onchain_metric_time', 'symbol', 'metric_name', 'timestamp'),
    )
