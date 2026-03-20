from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from shared.db.base import Base

class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False) # BUY, SELL, HOLD
    confidence = Column(Float)
    reasoning = Column(Text)
    model_used = Column(String) # e.g. "qwen-plus"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
