import { cn } from '@/lib/utils';
import type { SessionStatus, ExecutionStatus, DataFreshness, AgentStatus, AlertSeverity, MessageType } from '@/types';

// ─── Status Badge ──────────────────────────────────────────

const statusStyles: Record<string, string> = {
  // Session
  COMPLETED: 'bg-success/15 text-success border-success/30',
  RUNNING: 'bg-primary/15 text-primary border-primary/30 animate-pulse-glow',
  REJECTED: 'bg-danger/15 text-danger border-danger/30',
  FAILED: 'bg-danger/15 text-danger border-danger/30',
  // Execution
  ACCEPTED: 'bg-info/15 text-info border-info/30',
  PENDING: 'bg-warning/15 text-warning border-warning/30',
  FILLED: 'bg-success/15 text-success border-success/30',
  PARTIAL_FILLED: 'bg-warning/15 text-warning border-warning/30',
  // Data freshness
  fresh: 'bg-success/15 text-success border-success/30',
  stale: 'bg-stale/15 text-stale border-stale/30',
  degraded: 'bg-warning/15 text-warning border-warning/30',
  // Agent status
  online: 'bg-success/15 text-success border-success/30',
  offline: 'bg-danger/15 text-danger border-danger/30',
  processing: 'bg-primary/15 text-primary border-primary/30 animate-pulse-glow',
  // Risk gate
  passed: 'bg-success/15 text-success border-success/30',
  triggered: 'bg-danger/15 text-danger border-danger/30',
  warning: 'bg-warning/15 text-warning border-warning/30',
  // Alert severity
  info: 'bg-info/15 text-info border-info/30',
  critical: 'bg-danger/15 text-danger border-danger/30',
  // Message type
  think: 'bg-muted text-muted-foreground border-border',
  output: 'bg-primary/15 text-primary border-primary/30',
  error: 'bg-danger/15 text-danger border-danger/30',
};

type BadgeStatus = SessionStatus | ExecutionStatus | DataFreshness | AgentStatus | AlertSeverity | MessageType | 'passed' | 'triggered' | 'warning';

export function StatusBadge({ status, className }: { status: BadgeStatus; className?: string }) {
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border',
      statusStyles[status] || 'bg-muted text-muted-foreground border-border',
      className,
    )}>
      {status}
    </span>
  );
}

// ─── Metric Card ───────────────────────────────────────────

export function MetricCard({ label, value, sub, trend }: {
  label: string;
  value: string | number;
  sub?: string;
  trend?: 'up' | 'down' | 'neutral';
}) {
  const trendColor = trend === 'up' ? 'text-success' : trend === 'down' ? 'text-danger' : 'text-muted-foreground';
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs font-mono text-muted-foreground uppercase tracking-wider">{label}</p>
      <p className={cn('text-2xl font-mono font-bold mt-1', trendColor)}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  );
}

// ─── Section Panel ─────────────────────────────────────────

export function Panel({ title, children, className, actions }: {
  title: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className={cn('rounded-lg border border-border bg-card', className)}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h3 className="text-sm font-mono font-semibold text-foreground uppercase tracking-wider">{title}</h3>
        {actions}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

// ─── Confidence Bar ────────────────────────────────────────

export function ConfidenceBar({ value, className }: { value: number; className?: string }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? 'bg-success' : pct >= 60 ? 'bg-warning' : 'bg-danger';
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-muted-foreground w-8">{pct}%</span>
    </div>
  );
}

// ─── Agent Role Color Map ──────────────────────────────────

export const agentColorMap: Record<string, string> = {
  market: 'text-agent-market border-agent-market/30 bg-agent-market/10',
  macro: 'text-agent-macro border-agent-macro/30 bg-agent-macro/10',
  onchain: 'text-agent-onchain border-agent-onchain/30 bg-agent-onchain/10',
  sentiment: 'text-agent-sentiment border-agent-sentiment/30 bg-agent-sentiment/10',
  analyst: 'text-agent-analyst border-agent-analyst/30 bg-agent-analyst/10',
  bull_strategist: 'text-agent-bull border-agent-bull/30 bg-agent-bull/10',
  bear_strategist: 'text-agent-bear border-agent-bear/30 bg-agent-bear/10',
  portfolio_manager: 'text-agent-pm border-agent-pm/30 bg-agent-pm/10',
  reviewer: 'text-agent-reviewer border-agent-reviewer/30 bg-agent-reviewer/10',
  executor: 'text-agent-executor border-agent-executor/30 bg-agent-executor/10',
  reflector: 'text-agent-reflector border-agent-reflector/30 bg-agent-reflector/10',
};

export const agentBorderColor: Record<string, string> = {
  market: 'border-agent-market',
  macro: 'border-agent-macro',
  onchain: 'border-agent-onchain',
  sentiment: 'border-agent-sentiment',
  analyst: 'border-agent-analyst',
  bull_strategist: 'border-agent-bull',
  bear_strategist: 'border-agent-bear',
  portfolio_manager: 'border-agent-pm',
  reviewer: 'border-agent-reviewer',
  executor: 'border-agent-executor',
  reflector: 'border-agent-reflector',
};
