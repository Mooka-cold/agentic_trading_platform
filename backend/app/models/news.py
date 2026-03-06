from sqlalchemy import Column, String, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.models.user import Base # Use the same Base for simplicity if in same DB, or create new Base

class News(Base):
    __tablename__ = "news"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    summary = Column(Text)
    url = Column(String, unique=True, nullable=False) # Avoid duplicates
    source = Column(String) # e.g. "Cointelegraph", "CryptoPanic"
    published_at = Column(DateTime(timezone=True), default=func.now())
    sentiment = Column(String) # "positive", "negative", "neutral"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
