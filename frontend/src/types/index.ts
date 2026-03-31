// ─── Agent System Types ────────────────────────────────────

export type AgentRole =
  | 'market' | 'macro' | 'onchain' | 'sentiment'
  | 'analyst' | 'bull_strategist' | 'bear_strategist'
  | 'portfolio_manager' | 'reviewer' | 'executor' | 'reflector';

export type AgentStatus = 'online' | 'offline' | 'degraded' | 'processing';

export interface AgentInfo {
  id: string;
  role: AgentRole;
  name: string;
  status: AgentStatus;
  lastActive: string;
  confidence?: number;
}

// ─── Data Source Types ─────────────────────────────────────

export type DataFreshness = 'fresh' | 'stale' | 'degraded';

export interface DataSource {
  id: string;
  name: string;
  category: 'market' | 'macro' | 'onchain' | 'sentiment';
  freshness: DataFreshness;
  lastUpdated: string;
  latencyMs: number;
  errorRate: number;
}

// ─── Session & Orchestration ───────────────────────────────

export type SessionStatus = 'RUNNING' | 'COMPLETED' | 'REJECTED' | 'FAILED';

export type OrderType = 'MARKET' | 'LIMIT' | 'TWAP';
export type TradeAction = 'BUY' | 'SELL' | 'HOLD' | 'REDUCE' | 'LONG' | 'SHORT' | 'CLOSE';
export type ExecutionStatus = 'ACCEPTED' | 'PENDING' | 'FILLED' | 'PARTIAL_FILLED' | 'REJECTED';
export type RejectCode = 'RISK_LIMIT' | 'STALE_DATA' | 'LOW_CONFIDENCE' | 'POSITION_LIMIT' | 'DELEVERAGING' | null;

export interface OrchestrationConfig {
  max_revision_rounds: number;
  data_routing_policy: 'all_sources' | 'best_effort' | 'quorum';
  cross_examiner_enabled: boolean;
  hold_bias: number;
  risk_reduction_policy: 'conservative' | 'moderate' | 'aggressive';
  execution_constraints: {
    max_slippage_bps: number;
    max_position_pct: number;
    twap_duration_min: number;
  };
}

export interface RevisionRound {
  round: number;
  trigger: string;
  changes: string;
  timestamp: string;
}

// ─── Dialogue / Message Types ──────────────────────────────

export type MessageType = 'think' | 'output' | 'warning' | 'error';

export interface AgentMessage {
  id: string;
  sessionId: string;
  agentRole: AgentRole;
  agentName: string;
  messageType: MessageType;
  content: string;
  confidence?: number;
  reasoning?: string;
  timestamp: string;
  artifacts?: Record<string, unknown>;
}

export interface DebateExchange {
  bullArgument: AgentMessage;
  bearArgument: AgentMessage;
  pmVerdict: AgentMessage;
}

// ─── Trade & Execution ─────────────────────────────────────

export interface TradeRecord {
  id: string;
  sessionId: string;
  symbol: string;
  action: TradeAction;
  orderType: OrderType;
  triggerCondition: string;
  quantity: number;
  entryPrice: number;
  executedPrice: number | null;
  slippageBps: number | null;
  fee: number;
  pnl: number | null;
  status: ExecutionStatus;
  rejectCode: RejectCode;
  newBalance: number;
  timestamp: string;
}

// ─── Risk / Gate Types ─────────────────────────────────────

export interface RiskGate {
  name: string;
  type: 'safety_guard' | 'trade_gate' | 'onchain_gate' | 'deleveraging';
  status: 'passed' | 'triggered' | 'warning';
  detail: string;
  timestamp: string;
}

// ─── Session (Full) ────────────────────────────────────────

export interface Session {
  id: string;
  symbol: string;
  status: SessionStatus;
  startTime: string;
  endTime: string | null;
  orchestrationConfig: OrchestrationConfig;
  revisionRounds: RevisionRound[];
  messages: AgentMessage[];
  debate: DebateExchange | null;
  riskGates: RiskGate[];
  trade: TradeRecord | null;
  reflection: ReflectionEntry | null;
}

// ─── Reflection / Learning ─────────────────────────────────

export interface ReflectionEntry {
  id: string;
  sessionId: string;
  whatWentRight: string[];
  whatWentWrong: string[];
  improvements: string[];
  failureMode: string | null;
  ruleChanges: RuleChange[];
  timestamp: string;
}

export interface RuleChange {
  parameter: string;
  oldValue: string;
  newValue: string;
  reason: string;
  timestamp: string;
}

// ─── KPIs ──────────────────────────────────────────────────

export interface SystemKPIs {
  totalPnl: number;
  dailyPnl: number;
  maxDrawdown: number;
  winRate: number;
  currentLeverage: number;
  riskGateTriggeredCount: number;
  totalSessions: number;
  completedSessions: number;
  rejectedSessions: number;
  failedSessions: number;
}

// ─── Alert ─────────────────────────────────────────────────

export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface Alert {
  id: string;
  severity: AlertSeverity;
  title: string;
  detail: string;
  source: string;
  timestamp: string;
  acknowledged: boolean;
}
