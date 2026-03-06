from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class MarketData(BaseModel):
    symbol: str
    timeframe: str
    price: float
    volume: float
    indicators: Dict[str, float] = {}  # RSI, MACD, etc.
    news_sentiment: float = 0.0

class AnalystOutput(BaseModel):
    sentiment_score: float = Field(description="Score from -1.0 (Bearish) to 1.0 (Bullish)")
    summary: str = Field(description="Market summary (max 50 words)")
    trading_bias: str = Field(description="BULLISH | BEARISH | NEUTRAL")
    key_risk: str = Field(description="Current biggest risk factor")
    reasoning: str = Field(description="Step-by-step analysis chain")

class StrategyProposal(BaseModel):
    action: str = Field(description="BUY, SELL, SHORT, COVER, or HOLD")
    entry_price: Optional[float] = None
    quantity: Optional[float] = Field(description="Position size in base currency (e.g., BTC)", default=None)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str
    confidence: float
    assumptions: List[str] = Field(default_factory=list)

class RiskVerdict(BaseModel):
    approved: bool
    risk_score: float  # 0-100 (Higher is riskier)
    adjusted_size: Optional[float] = None
    message: str
    reject_code: Optional[str] = None
    fix_suggestions: Dict[str, Any] = Field(default_factory=dict)
    checks: Dict[str, str] = Field(default_factory=dict)

class AgentLog(BaseModel):
    agent_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: str
    type: str = "process"  # input, process, output

class SentimentOutput(BaseModel):
    score: float = Field(description="Score from -1.0 (Extreme Fear/Bearish) to 1.0 (Extreme Greed/Bullish)")
    summary: str = Field(description="Summary of news and social sentiment")
    key_drivers: List[str] = Field(description="List of main events driving sentiment")

class AgentState(BaseModel):
    # --- Context (Input) ---
    session_id: str
    market_data: MarketData
    account_balance: float = 0.0
    positions: list[Dict[str, Any]] = []
    
    # --- Agent Outputs (Mutable State) ---
    analyst_report: Optional[AnalystOutput] = None
    sentiment_report: Optional[SentimentOutput] = None  # <--- New Field
    strategy_proposal: Optional[StrategyProposal] = None
    risk_verdict: Optional[RiskVerdict] = None
    review_feedback: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None  # <--- New Field for Execution Result
    strategy_revision_round: int = 0
    
    # --- Meta ---
    logs: List[AgentLog] = []
    status: str = "running"
    current_step: str = "init"
    
    def add_log(self, agent_id: str, content: str, log_type: str = "process"):
        self.logs.append(AgentLog(agent_id=agent_id, content=content, type=log_type))
