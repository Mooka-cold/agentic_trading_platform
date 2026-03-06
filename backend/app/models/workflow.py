from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum
import uuid

class WorkflowStatus(enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class WorkflowSession(Base):
    __tablename__ = "workflow_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String, nullable=False)
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.PENDING)
    start_time = Column(DateTime, server_default=func.now())
    end_time = Column(DateTime, nullable=True)
    
    # New fields for filtering
    action = Column(String, nullable=True) # BUY, SELL, HOLD
    review_status = Column(String, nullable=True) # APPROVED, REJECTED, SKIPPED
    periodic_review_status = Column(String, default="PENDING") # PENDING, T1_DONE, T6_DONE, COMPLETED
    
    logs = relationship("AgentLog", back_populates="session", cascade="all, delete-orphan")

class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("workflow_sessions.id"), nullable=False)
    agent_id = Column(String, nullable=False) # 'analyst', 'strategist'
    log_type = Column(String, default="process") # 'process', 'output', 'error'
    content = Column(Text, nullable=True)
    artifact = Column(JSON, nullable=True) # Structured output
    created_at = Column(DateTime, server_default=func.now())
    
    session = relationship("WorkflowSession", back_populates="logs")
