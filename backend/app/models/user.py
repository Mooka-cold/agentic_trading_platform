from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=True) # Optional for wallet users
    hashed_password = Column(String, nullable=True) # Optional for wallet users
    wallet_address = Column(String, unique=True, index=True, nullable=True) # Wallet address (0x...)
    nonce = Column(String, nullable=True) # For SIWE verification
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    strategies = relationship("Strategy", back_populates="owner")

class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    name = Column(String, nullable=False)
    description = Column(String)
    prompt_template = Column(String) # The LLM Prompt
    config = Column(JSON) # JSON config for parameters
    status = Column(String, default="active") # active, paused, backtesting
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="strategies")
    orders = relationship("Order", back_populates="strategy")

class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"))
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False) # BUY, SELL
    order_type = Column(String, default="MARKET") # LIMIT, MARKET
    price = Column(String) # Decimal as string
    amount = Column(String) # Decimal as string
    status = Column(String, default="pending") # pending, filled, failed
    exchange_order_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    strategy = relationship("Strategy", back_populates="orders")
