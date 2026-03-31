import type {
  AgentInfo, DataSource, Session, SystemKPIs, Alert,
  OrchestrationConfig, AgentMessage, DebateExchange,
  TradeRecord, RiskGate, ReflectionEntry, RevisionRound,
} from '@/types';

// ─── Agents ────────────────────────────────────────────────

export const mockAgents: AgentInfo[] = [
  { id: 'a1', role: 'market', name: 'Market Scanner', status: 'online', lastActive: '2025-03-27T10:30:00Z', confidence: 0.92 },
  { id: 'a2', role: 'macro', name: 'Macro Analyst', status: 'online', lastActive: '2025-03-27T10:28:00Z', confidence: 0.88 },
  { id: 'a3', role: 'onchain', name: 'Onchain Monitor', status: 'degraded', lastActive: '2025-03-27T10:25:00Z', confidence: 0.75 },
  { id: 'a4', role: 'sentiment', name: 'Sentiment Gauge', status: 'online', lastActive: '2025-03-27T10:29:00Z', confidence: 0.85 },
  { id: 'a5', role: 'analyst', name: 'Chief Analyst', status: 'online', lastActive: '2025-03-27T10:30:00Z', confidence: 0.90 },
  { id: 'a6', role: 'bull_strategist', name: 'Bull Strategist', status: 'online', lastActive: '2025-03-27T10:30:00Z', confidence: 0.82 },
  { id: 'a7', role: 'bear_strategist', name: 'Bear Strategist', status: 'online', lastActive: '2025-03-27T10:30:00Z', confidence: 0.78 },
  { id: 'a8', role: 'portfolio_manager', name: 'Portfolio Manager', status: 'online', lastActive: '2025-03-27T10:30:00Z', confidence: 0.91 },
  { id: 'a9', role: 'reviewer', name: 'Risk Reviewer', status: 'online', lastActive: '2025-03-27T10:30:00Z', confidence: 0.95 },
  { id: 'a10', role: 'executor', name: 'Trade Executor', status: 'online', lastActive: '2025-03-27T10:30:00Z' },
  { id: 'a11', role: 'reflector', name: 'Reflector', status: 'online', lastActive: '2025-03-27T10:30:00Z' },
];

// ─── Data Sources ──────────────────────────────────────────

export const mockDataSources: DataSource[] = [
  { id: 'd1', name: 'Binance WebSocket', category: 'market', freshness: 'fresh', lastUpdated: '2025-03-27T10:30:00Z', latencyMs: 12, errorRate: 0.001 },
  { id: 'd2', name: 'CoinGecko API', category: 'market', freshness: 'fresh', lastUpdated: '2025-03-27T10:29:30Z', latencyMs: 230, errorRate: 0.005 },
  { id: 'd3', name: 'FRED Economic Data', category: 'macro', freshness: 'fresh', lastUpdated: '2025-03-27T08:00:00Z', latencyMs: 450, errorRate: 0.002 },
  { id: 'd4', name: 'Treasury Yield Feed', category: 'macro', freshness: 'stale', lastUpdated: '2025-03-26T16:00:00Z', latencyMs: 800, errorRate: 0.01 },
  { id: 'd5', name: 'Glassnode', category: 'onchain', freshness: 'degraded', lastUpdated: '2025-03-27T09:00:00Z', latencyMs: 1200, errorRate: 0.08 },
  { id: 'd6', name: 'Dune Analytics', category: 'onchain', freshness: 'fresh', lastUpdated: '2025-03-27T10:15:00Z', latencyMs: 340, errorRate: 0.003 },
  { id: 'd7', name: 'LunarCrush', category: 'sentiment', freshness: 'fresh', lastUpdated: '2025-03-27T10:28:00Z', latencyMs: 180, errorRate: 0.004 },
  { id: 'd8', name: 'Twitter/X Firehose', category: 'sentiment', freshness: 'fresh', lastUpdated: '2025-03-27T10:30:00Z', latencyMs: 95, errorRate: 0.006 },
];

// ─── Orchestration Config ──────────────────────────────────

export const mockOrchConfig: OrchestrationConfig = {
  max_revision_rounds: 3,
  data_routing_policy: 'best_effort',
  cross_examiner_enabled: true,
  hold_bias: 0.15,
  risk_reduction_policy: 'conservative',
  execution_constraints: {
    max_slippage_bps: 25,
    max_position_pct: 5,
    twap_duration_min: 15,
  },
};

// ─── Mock Messages for a session ───────────────────────────

const s1Messages: AgentMessage[] = [
  { id: 'm1', sessionId: 'sess-001', agentRole: 'market', agentName: 'Market Scanner', messageType: 'output', content: 'BTC showing bullish breakout above 68,200 with volume surge. RSI at 62, MACD histogram expanding. 4H trend firmly bullish.', confidence: 0.92, timestamp: '2025-03-27T10:00:00Z' },
  { id: 'm2', sessionId: 'sess-001', agentRole: 'macro', agentName: 'Macro Analyst', messageType: 'output', content: 'Fed minutes indicate dovish tilt. DXY weakening at 103.2. Risk-on environment favorable for crypto. Treasury yields declining.', confidence: 0.88, timestamp: '2025-03-27T10:00:15Z' },
  { id: 'm3', sessionId: 'sess-001', agentRole: 'onchain', agentName: 'Onchain Monitor', messageType: 'warning', content: 'Exchange reserves declining (bullish). However, whale wallets showing mixed signals - 3 large deposits to Binance in last 2h. Data degraded from Glassnode.', confidence: 0.75, timestamp: '2025-03-27T10:00:30Z' },
  { id: 'm4', sessionId: 'sess-001', agentRole: 'sentiment', agentName: 'Sentiment Gauge', messageType: 'output', content: 'Social sentiment strongly bullish. Fear & Greed at 72 (Greed). CT consensus is "breakout confirmed". Contrarian signal: crowded long.', confidence: 0.85, timestamp: '2025-03-27T10:00:45Z' },
  { id: 'm5', sessionId: 'sess-001', agentRole: 'analyst', agentName: 'Chief Analyst', messageType: 'think', content: 'Consolidating inputs: 3/4 sources bullish, onchain degraded but leaning bullish. Macro supportive. Key risk: crowded sentiment may indicate local top.', confidence: 0.90, reasoning: 'Weighted signal aggregation with data quality penalty on onchain source.', timestamp: '2025-03-27T10:01:00Z' },
  { id: 'm6', sessionId: 'sess-001', agentRole: 'analyst', agentName: 'Chief Analyst', messageType: 'output', content: 'SIGNAL: Moderately Bullish on BTC. Confidence 0.82. Recommend position increase with tight stops. Key level: 68,200 support.', confidence: 0.82, timestamp: '2025-03-27T10:01:15Z' },
  { id: 'm7', sessionId: 'sess-001', agentRole: 'bull_strategist', agentName: 'Bull Strategist', messageType: 'output', content: 'LONG BTC. Entry at 68,450 via TWAP over 15min. Target 72,000 (+5.2%). Rationale: breakout confirmed, macro tailwind, declining exchange reserves. Position: 4% of portfolio.', confidence: 0.82, reasoning: 'Technical breakout + macro alignment + onchain supply squeeze', timestamp: '2025-03-27T10:02:00Z' },
  { id: 'm8', sessionId: 'sess-001', agentRole: 'bear_strategist', agentName: 'Bear Strategist', messageType: 'output', content: 'CAUTION. Sentiment too crowded (F&G 72). Whale deposits suggest distribution. If breakdown below 67,800 → crash to 64,000. Recommend HOLD or small position only (2% max). Onchain data degraded - unreliable signal.', confidence: 0.78, reasoning: 'Crowded sentiment + whale distribution pattern + degraded data quality', timestamp: '2025-03-27T10:02:15Z' },
  { id: 'm9', sessionId: 'sess-001', agentRole: 'portfolio_manager', agentName: 'Portfolio Manager', messageType: 'think', content: 'Bull case stronger on technicals and macro. Bear raises valid concern on sentiment crowding. Compromise: take position but reduce size from 4% to 3%. Use TWAP for better execution. Set stop at 67,500.', timestamp: '2025-03-27T10:03:00Z' },
  { id: 'm10', sessionId: 'sess-001', agentRole: 'portfolio_manager', agentName: 'Portfolio Manager', messageType: 'output', content: 'VERDICT: BUY BTC. Size: 3% portfolio. Entry: TWAP 68,450 over 15min. Stop: 67,500. Target: 71,500. Rationale: Bull thesis accepted with size reduction per Bear crowding concern.', confidence: 0.91, timestamp: '2025-03-27T10:03:15Z' },
  { id: 'm11', sessionId: 'sess-001', agentRole: 'reviewer', agentName: 'Risk Reviewer', messageType: 'output', content: 'APPROVED. All risk gates passed. Position within limits (3% < 5% max). Leverage acceptable (1.2x). Slippage budget 25bps adequate for BTC liquidity. Note: monitor onchain data quality - currently degraded.', confidence: 0.95, timestamp: '2025-03-27T10:04:00Z' },
  { id: 'm12', sessionId: 'sess-001', agentRole: 'executor', agentName: 'Trade Executor', messageType: 'output', content: 'TWAP order initiated. 0.45 BTC over 15min. First fill: 0.15 BTC @ 68,462. Slippage: 1.7bps. Continuing execution...', timestamp: '2025-03-27T10:05:00Z' },
  { id: 'm13', sessionId: 'sess-001', agentRole: 'executor', agentName: 'Trade Executor', messageType: 'output', content: 'TWAP complete. Total filled: 0.45 BTC. VWAP: 68,478. Total slippage: 4.1bps. Fee: $12.30. Status: FILLED.', timestamp: '2025-03-27T10:20:00Z' },
];

const s1Debate: DebateExchange = {
  bullArgument: s1Messages[6],
  bearArgument: s1Messages[7],
  pmVerdict: s1Messages[9],
};

const s1RiskGates: RiskGate[] = [
  { name: 'Position Limit', type: 'safety_guard', status: 'passed', detail: '3% < 5% max position', timestamp: '2025-03-27T10:04:00Z' },
  { name: 'Leverage Check', type: 'safety_guard', status: 'passed', detail: '1.2x < 3x max leverage', timestamp: '2025-03-27T10:04:00Z' },
  { name: 'Data Quality Gate', type: 'onchain_gate', status: 'warning', detail: 'Onchain source degraded but non-blocking', timestamp: '2025-03-27T10:04:00Z' },
  { name: 'Slippage Budget', type: 'trade_gate', status: 'passed', detail: '25bps budget for TWAP execution', timestamp: '2025-03-27T10:04:00Z' },
];

const s1Trade: TradeRecord = {
  id: 't1', sessionId: 'sess-001', symbol: 'BTC', action: 'BUY', orderType: 'TWAP',
  triggerCondition: 'Breakout above 68,200 confirmed', quantity: 0.45,
  entryPrice: 68450, executedPrice: 68478, slippageBps: 4.1, fee: 12.30,
  pnl: 342.50, status: 'FILLED', rejectCode: null, newBalance: 105342.50,
  timestamp: '2025-03-27T10:20:00Z',
};

const s1Reflection: ReflectionEntry = {
  id: 'r1', sessionId: 'sess-001',
  whatWentRight: ['Correctly identified breakout with macro tailwind', 'TWAP execution minimized slippage to 4.1bps', 'Size reduction from 4% to 3% was prudent given crowded sentiment'],
  whatWentWrong: ['Onchain data was degraded - should have weighted down further', 'Did not account for funding rate (currently elevated at 0.03%)'],
  improvements: ['Add funding rate to analyst inputs', 'Implement automatic confidence penalty when any source is degraded', 'Consider reducing position further when F&G > 70'],
  failureMode: null,
  ruleChanges: [
    { parameter: 'degraded_source_penalty', oldValue: '0.1', newValue: '0.15', reason: 'Insufficient penalty for degraded onchain data', timestamp: '2025-03-27T10:25:00Z' },
  ],
  timestamp: '2025-03-27T10:25:00Z',
};

// ─── Session 2: Rejected ───────────────────────────────────

const s2Messages: AgentMessage[] = [
  { id: 'm20', sessionId: 'sess-002', agentRole: 'market', agentName: 'Market Scanner', messageType: 'output', content: 'ETH range-bound at 3,450-3,520. Low volume, no clear direction. Bollinger bands squeezing.', confidence: 0.65, timestamp: '2025-03-27T09:00:00Z' },
  { id: 'm21', sessionId: 'sess-002', agentRole: 'macro', agentName: 'Macro Analyst', messageType: 'output', content: 'Neutral macro environment. No significant catalysts today. CPI report tomorrow may cause volatility.', confidence: 0.70, timestamp: '2025-03-27T09:00:15Z' },
  { id: 'm22', sessionId: 'sess-002', agentRole: 'analyst', agentName: 'Chief Analyst', messageType: 'output', content: 'SIGNAL: Neutral on ETH. Confidence 0.55. Insufficient conviction for directional trade. Recommend HOLD.', confidence: 0.55, timestamp: '2025-03-27T09:01:00Z' },
  { id: 'm23', sessionId: 'sess-002', agentRole: 'bull_strategist', agentName: 'Bull Strategist', messageType: 'output', content: 'Weak LONG case. BB squeeze could break up. But confidence too low for meaningful position.', confidence: 0.52, timestamp: '2025-03-27T09:02:00Z' },
  { id: 'm24', sessionId: 'sess-002', agentRole: 'bear_strategist', agentName: 'Bear Strategist', messageType: 'output', content: 'No strong SHORT case either. Pre-CPI uncertainty suggests staying flat.', confidence: 0.48, timestamp: '2025-03-27T09:02:15Z' },
  { id: 'm25', sessionId: 'sess-002', agentRole: 'portfolio_manager', agentName: 'Portfolio Manager', messageType: 'output', content: 'VERDICT: HOLD. No trade. Both strategists below conviction threshold. Wait for CPI catalyst.', confidence: 0.60, timestamp: '2025-03-27T09:03:00Z' },
  { id: 'm26', sessionId: 'sess-002', agentRole: 'reviewer', agentName: 'Risk Reviewer', messageType: 'output', content: 'CONFIRMED: HOLD decision appropriate. Low confidence environment.', confidence: 0.95, timestamp: '2025-03-27T09:04:00Z' },
];

// ─── Session 3: Failed / Risk Rejected ─────────────────────

const s3Messages: AgentMessage[] = [
  { id: 'm30', sessionId: 'sess-003', agentRole: 'market', agentName: 'Market Scanner', messageType: 'output', content: 'SOL flash crash -8% in 5 minutes. Volume 5x average. Liquidation cascade detected.', confidence: 0.90, timestamp: '2025-03-27T08:00:00Z' },
  { id: 'm31', sessionId: 'sess-003', agentRole: 'onchain', agentName: 'Onchain Monitor', messageType: 'error', content: 'CRITICAL: Glassnode API timeout. Onchain data unavailable for SOL. Falling back to cached data (2h old).', confidence: 0.30, timestamp: '2025-03-27T08:00:10Z' },
  { id: 'm32', sessionId: 'sess-003', agentRole: 'analyst', agentName: 'Chief Analyst', messageType: 'warning', content: 'ALERT: Operating with stale onchain data. Signal reliability significantly reduced. Confidence penalty applied.', confidence: 0.45, timestamp: '2025-03-27T08:01:00Z' },
  { id: 'm33', sessionId: 'sess-003', agentRole: 'bull_strategist', agentName: 'Bull Strategist', messageType: 'output', content: 'Potential dip buy opportunity at $142. But data quality too low for confident entry.', confidence: 0.40, timestamp: '2025-03-27T08:02:00Z' },
  { id: 'm34', sessionId: 'sess-003', agentRole: 'bear_strategist', agentName: 'Bear Strategist', messageType: 'output', content: 'Liquidation cascade may continue. Strongly advise against buying the dip. SELL or REDUCE existing position.', confidence: 0.72, timestamp: '2025-03-27T08:02:15Z' },
  { id: 'm35', sessionId: 'sess-003', agentRole: 'portfolio_manager', agentName: 'Portfolio Manager', messageType: 'output', content: 'VERDICT: REDUCE SOL position by 50%. Bear thesis compelling during liquidation cascade. Data quality too poor for aggressive action.', confidence: 0.68, timestamp: '2025-03-27T08:03:00Z' },
  { id: 'm36', sessionId: 'sess-003', agentRole: 'reviewer', agentName: 'Risk Reviewer', messageType: 'error', content: 'REJECTED: Stale data gate triggered. Cannot execute with onchain data >1h stale. Entering deleveraging mode for SOL.', confidence: 0.95, timestamp: '2025-03-27T08:04:00Z' },
];

// ─── Assemble Sessions ─────────────────────────────────────

export const mockSessions: Session[] = [
  {
    id: 'sess-001', symbol: 'BTC', status: 'COMPLETED',
    startTime: '2025-03-27T10:00:00Z', endTime: '2025-03-27T10:25:00Z',
    orchestrationConfig: mockOrchConfig,
    revisionRounds: [
      { round: 1, trigger: 'Bear raised crowding concern', changes: 'Reduced position size from 4% to 3%', timestamp: '2025-03-27T10:03:00Z' },
    ],
    messages: s1Messages, debate: s1Debate, riskGates: s1RiskGates,
    trade: s1Trade, reflection: s1Reflection,
  },
  {
    id: 'sess-002', symbol: 'ETH', status: 'COMPLETED',
    startTime: '2025-03-27T09:00:00Z', endTime: '2025-03-27T09:05:00Z',
    orchestrationConfig: mockOrchConfig,
    revisionRounds: [],
    messages: s2Messages, debate: { bullArgument: s2Messages[3], bearArgument: s2Messages[4], pmVerdict: s2Messages[5] },
    riskGates: [
      { name: 'Confidence Gate', type: 'trade_gate', status: 'passed', detail: 'HOLD decision - no trade to gate', timestamp: '2025-03-27T09:04:00Z' },
    ],
    trade: null, reflection: null,
  },
  {
    id: 'sess-003', symbol: 'SOL', status: 'REJECTED',
    startTime: '2025-03-27T08:00:00Z', endTime: '2025-03-27T08:05:00Z',
    orchestrationConfig: mockOrchConfig,
    revisionRounds: [],
    messages: s3Messages,
    debate: { bullArgument: s3Messages[3], bearArgument: s3Messages[4], pmVerdict: s3Messages[5] },
    riskGates: [
      { name: 'Data Quality Gate', type: 'onchain_gate', status: 'triggered', detail: 'Onchain data stale >1h. Blocking execution.', timestamp: '2025-03-27T08:04:00Z' },
      { name: 'Deleveraging Mode', type: 'deleveraging', status: 'triggered', detail: 'Auto-deleveraging activated for SOL position', timestamp: '2025-03-27T08:04:00Z' },
    ],
    trade: null,
    reflection: {
      id: 'r3', sessionId: 'sess-003',
      whatWentRight: ['Stale data gate correctly blocked execution', 'Deleveraging mode activated appropriately'],
      whatWentWrong: ['Glassnode API single point of failure', 'No fallback onchain data source for SOL'],
      improvements: ['Add redundant onchain data provider', 'Implement circuit breaker for API failures', 'Pre-cache critical onchain metrics'],
      failureMode: 'stale_data',
      ruleChanges: [],
      timestamp: '2025-03-27T08:10:00Z',
    },
  },
];

// ─── KPIs ──────────────────────────────────────────────────

export const mockKPIs: SystemKPIs = {
  totalPnl: 12450.80,
  dailyPnl: 342.50,
  maxDrawdown: -3.2,
  winRate: 0.68,
  currentLeverage: 1.2,
  riskGateTriggeredCount: 7,
  totalSessions: 156,
  completedSessions: 128,
  rejectedSessions: 18,
  failedSessions: 10,
};

// ─── Alerts ────────────────────────────────────────────────

export const mockAlerts: Alert[] = [
  { id: 'al1', severity: 'warning', title: 'Stale Data: Treasury Yield', detail: 'Treasury yield feed last updated 18h ago', source: 'FRED', timestamp: '2025-03-27T10:00:00Z', acknowledged: false },
  { id: 'al2', severity: 'critical', title: 'API Failure: Glassnode', detail: 'Glassnode API returning 503 errors. Onchain data degraded.', source: 'Glassnode', timestamp: '2025-03-27T08:00:00Z', acknowledged: true },
  { id: 'al3', severity: 'warning', title: 'Risk Gate Triggered', detail: 'Stale data gate blocked SOL trade execution', source: 'Risk Reviewer', timestamp: '2025-03-27T08:04:00Z', acknowledged: false },
  { id: 'al4', severity: 'info', title: 'Deleveraging Activated', detail: 'Auto-deleveraging mode for SOL due to data quality issues', source: 'System', timestamp: '2025-03-27T08:04:30Z', acknowledged: false },
];
