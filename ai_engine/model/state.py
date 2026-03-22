from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class MarketData(BaseModel):
    symbol: str
    timeframe: str
    price: float
    volume: float
    indicators: Dict[str, Any] = {}  # RSI, MACD(dict), BB(dict), etc.

class AnalystOutput(BaseModel):
    sentiment_score: float = Field(description="Score from -1.0 (Bearish) to 1.0 (Bullish)")
    confidence: float = Field(default=0.5, description="Confidence from 0.0 to 1.0")
    summary: str = Field(description="Market summary (max 50 words)")
    trading_bias: str = Field(description="BULLISH | BEARISH | NEUTRAL")
    key_risk: str = Field(description="Current biggest risk factor")
    reasoning: str = Field(description="Step-by-step analysis chain")

class StrategyProposal(BaseModel):
    action: str = Field(description="BUY, SELL, SHORT, COVER, or HOLD")
    order_type: str = Field(default="MARKET", description="MARKET | LIMIT | STOP")
    trigger_condition: Optional[str] = None
    entry_price: Optional[float] = None
    quantity: Optional[float] = Field(description="Position size in base currency (e.g., BTC)", default=None)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str
    confidence: float
    self_check: Optional[Dict[str, Any]] = None # New field for risk self-check
    assumptions: List[str] = Field(default_factory=list)

class RiskVerdict(BaseModel):
    approved: bool
    risk_score: float  # 0-100 (Higher is riskier)
    asset_class_identified: Optional[str] = Field(description="Detected asset class (e.g. Major Crypto)", default=None)
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
    llm_score: float = Field(description="LLM-only score from -1.0 to 1.0")
    rule_score: float = Field(description="Rule-engine score from -1.0 to 1.0")
    confidence: float = Field(description="Confidence from 0.0 to 1.0")
    summary: str = Field(description="Summary of news and social sentiment")
    key_drivers: List[str] = Field(description="List of main events driving sentiment")
    source_breakdown: Dict[str, float] = Field(default_factory=dict, description="Per-source weighted contribution")
    trade_gate: str = Field(default="normal")
    trigger_reason: Optional[str] = None
    urgent_event: bool = False
    sample_count: int = 0
    aggregation_conflicts: List[str] = Field(default_factory=list)

class CrossMarketImpact(BaseModel):
    market: str
    direction: str
    magnitude: float
    horizon: str
    confidence: float
    reason: str

class ImpactTag(BaseModel):
    asset_cluster: str
    factor: str
    direction: str
    magnitude: float
    confidence: float
    reason: str

class NewsInterpretationOutput(BaseModel):
    bias: str
    magnitude: float
    confidence: float
    severity: str
    event_type_l1: str
    event_type_l2: str
    summary_cn: str
    asset_mentions: List[str] = Field(default_factory=list)
    asset_clusters: List[str] = Field(default_factory=list)
    factor_tags: List[str] = Field(default_factory=list)
    impact_tags: List[ImpactTag] = Field(default_factory=list)
    mapping_version: str = "taxonomy_v1"
    cross_market_impacts: List[CrossMarketImpact] = Field(default_factory=list)
    evidence_quotes: List[str] = Field(default_factory=list)
    noise_flags: List[str] = Field(default_factory=list)
    final_status: str

class MacroOutput(BaseModel):
    regime: str = Field(description="RISK_ON | RISK_OFF | NEUTRAL")
    risk_score: int = Field(description="Risk Score (-5 to +5). Higher is riskier (Risk Off).")
    key_factors: List[str] = Field(description="Reasons for the regime classification")
    data_summary: Dict[str, Any] = Field(description="Raw data summary (e.g. DXY trend)")

class OnChainOutput(BaseModel):
    signal: str = Field(description="BULLISH | BEARISH | NEUTRAL")
    score: int = Field(description="Score -5 to +5")
    metrics: Dict[str, Any] = Field(description="Raw metrics (OI, LS_Ratio)")
    analysis: str = Field(description="Analysis reasoning")

class TrendFollowerOutput(BaseModel):
    signal: str = Field(description="BULLISH | BEARISH | NEUTRAL")
    confidence: float = Field(description="0.0 to 1.0")
    structure: str = Field(description="Market Structure: HH/HL (Bullish), LL/LH (Bearish), or Ranging")
    key_level: float = Field(description="Key support/resistance level identified")
    reasoning: str = Field(description="Trend analysis reasoning")

class MeanReversionOutput(BaseModel):
    signal: str = Field(description="OVERBOUGHT | OVERSOLD | NEUTRAL")
    deviation_score: float = Field(description="0.0 (Mean) to 1.0 (Extreme Deviation)")
    target_price: float = Field(description="Potential reversion target (e.g. MA20)")
    reasoning: str = Field(description="Reversion analysis reasoning")

class VolatilityHunterOutput(BaseModel):
    regime: str = Field(description="EXPANSION | COMPRESSION | STABLE")
    sqz_score: float = Field(description="Squeeze Score: 0 (No Squeeze) to 1 (Tight Squeeze)")
    expected_move: float = Field(description="Expected move magnitude in %")
    reasoning: str = Field(description="Volatility analysis reasoning")

class AgentState(BaseModel):
    # --- Context (Input) ---
    session_id: str
    market_data: MarketData
    account_balance: float = 0.0
    positions: list[Dict[str, Any]] = []
    market_regime: Optional[Dict[str, Any]] = None
    microstructure: Optional[Dict[str, Any]] = None
    portfolio_context: Optional[Dict[str, Any]] = None
    execution_constraints: Optional[Dict[str, Any]] = None
    unresolved_todos: List[str] = Field(default_factory=list)
    
    # --- Agent Outputs (Mutable State) ---
    analyst_report: Optional[AnalystOutput] = None
    sentiment_report: Optional[SentimentOutput] = None
    macro_report: Optional[MacroOutput] = None
    onchain_report: Optional[OnChainOutput] = None
    
    # Phase 4: Multi-Agent Debate
    bull_proposal: Optional[StrategyProposal] = None
    bear_proposal: Optional[StrategyProposal] = None
    
    strategy_proposal: Optional[StrategyProposal] = None # The final chosen proposal by PM
    risk_verdict: Optional[RiskVerdict] = None
    review_feedback: Optional[Dict[str, Any]] = None
    analyst_feedback: Optional[str] = None # Strategist's question to Analyst
    execution_result: Optional[Dict[str, Any]] = None  # <--- New Field for Execution Result
    strategy_revision_round: int = 0
    
    # --- Meta ---
    logs: List[AgentLog] = []
    status: str = "running"
    current_step: str = "init"
    
    def add_log(self, agent_id: str, content: str, log_type: str = "process"):
        self.logs.append(AgentLog(agent_id=agent_id, content=content, type=log_type))
