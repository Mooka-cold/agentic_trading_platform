from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from shared.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    wallet_address = Column(String, unique=True, index=True, nullable=True)
    nonce = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    prompts = relationship("UserPrompt", back_populates="owner")
    automation_rules = relationship("UserAutomationRule", back_populates="owner")

class UserPrompt(Base):
    __tablename__ = "user_prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_role = Column(String, nullable=False, index=True) # e.g., 'bull_strategist', 'analyst'
    system_prompt_override = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="prompts")

class SystemPersona(Base):
    __tablename__ = "system_personas"

    id = Column(String, primary_key=True) # e.g., 'warren_buffett', 'justin_sun'
    name = Column(String, nullable=False) # e.g., '巴菲特 (Warren Buffett)'
    role_type = Column(String, nullable=False, index=True) # 'MARKET', 'DECISION', 'ARBITRATOR', 'RISK', 'EXECUTION'
    description = Column(String, nullable=True)
    prompt_template = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserTeamConfig(Base):
    __tablename__ = "user_team_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    
    # Stores lists of persona IDs for each stage
    market_agent_ids = Column(JSON, default=list) # e.g., ["ray_dalio", "cathie_wood"] 行情分析师
    strategy_agent_ids = Column(JSON, default=list) # e.g., ["buffett", "justin_sun"] 策略大师（多种投资哲学）
    risk_agent_ids = Column(JSON, default=list) # e.g., ["howard_marks", "charlie_munger"] 风控官（多签共识）

    # Stores single persona ID for final decision
    finalizer_agent_id = Column(String, nullable=True) # e.g., "charlie_munger" 终极拍板人

    # Execution field is hidden from UI in v1; keep column for backward compatibility.
    execution_agent_id = Column(String, nullable=True) # e.g., "algo_twap_bot"

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserAutomationRule(Base):
    __tablename__ = "user_automation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String, nullable=False, index=True)
    rule_type = Column(String, nullable=False, index=True) # 'CRON', 'INDICATOR', 'NEWS'
    condition_payload = Column(JSON, nullable=False) # e.g. {"indicator": "RSI", "operator": "<", "value": 30}
    action_payload = Column(JSON, nullable=True) # Extra params for workflow
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="automation_rules")
