import { mockAgents, mockDataSources, mockKPIs, mockAlerts, mockSessions } from '@/data/mock';
import { StatusBadge, MetricCard, Panel, ConfidenceBar, agentColorMap } from '@/components/shared/StatusBadge';
import { cn } from '@/lib/utils';
import { AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react';
import { useEffect, useState } from 'react';
import { fetchPaperAccount, fetchSessions } from '@/data/api';
import { formatTimeCN } from '@/lib/time';

export default function OverviewPage() {
  const [kpis, setKpis] = useState(mockKPIs);
  const [sessions, setSessions] = useState(mockSessions);

  useEffect(() => {
    // Fetch real data on mount
    fetchPaperAccount()
      .then(realKpis => {
        setKpis(prev => ({
          ...prev,
          totalPnl: realKpis.totalPnl,
          dailyPnl: realKpis.dailyPnl,
        }));
      })
      .catch(err => console.error("Error fetching paper account:", err));

    fetchSessions()
      .then(realSessions => {
        // Map backend session data to frontend format
        const mappedSessions = realSessions.map(rs => ({
          id: rs.id,
          symbol: rs.symbol,
          status: rs.status,
          startTime: rs.start_time,
          endTime: rs.end_time,
          trade: { action: rs.action || 'HOLD', pnl: 0 }, // Simplified
          orchestrationConfig: mockSessions[0].orchestrationConfig,
          revisionRounds: [],
          messages: [],
          debate: { bullArgument: null, bearArgument: null, pmVerdict: null },
          riskGates: [],
          reflection: null,
        }));
        setSessions(mappedSessions.slice(0, 5)); // Keep latest 5
      })
      .catch(err => console.error("Error fetching sessions:", err));
  }, []);

  return (
    <div className="space-y-6 animate-slide-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-mono font-bold text-foreground">System Overview</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">Real-time agent trading system status</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-success animate-pulse-glow" />
          <span className="text-xs font-mono text-success">LIVE</span>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard label="Total PnL" value={`$${kpis.totalPnl.toLocaleString()}`} trend="up" />
        <MetricCard label="Daily PnL" value={`$${kpis.dailyPnl.toLocaleString()}`} trend="up" />
        <MetricCard label="Max Drawdown" value={`${kpis.maxDrawdown}%`} trend="down" />
        <MetricCard label="Win Rate" value={`${(kpis.winRate * 100).toFixed(0)}%`} trend="up" />
        <MetricCard label="Leverage" value={`${kpis.currentLeverage}x`} trend="neutral" />
        <MetricCard label="Risk Gates Hit" value={kpis.riskGateTriggeredCount} sub={`of ${kpis.totalSessions} sessions`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Agent Status Matrix */}
        <Panel title="Agent Status" className="lg:col-span-1">
          <div className="space-y-2">
            {mockAgents.map((agent) => (
              <div key={agent.id} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
                <div className="flex items-center gap-2">
                  <div className={cn('h-1.5 w-1.5 rounded-full', agent.status === 'online' ? 'bg-success' : agent.status === 'degraded' ? 'bg-warning' : 'bg-danger')} />
                  <span className={cn('text-xs font-mono', agentColorMap[agent.role]?.split(' ')[0])}>{agent.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  {agent.confidence !== undefined && <ConfidenceBar value={agent.confidence} className="w-16" />}
                  <StatusBadge status={agent.status} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* Data Source Freshness */}
        <Panel title="Data Sources" className="lg:col-span-1">
          <div className="space-y-2">
            {mockDataSources.map((src) => (
              <div key={src.id} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
                <div>
                  <p className="text-xs font-mono text-foreground">{src.name}</p>
                  <p className="text-[10px] font-mono text-muted-foreground">{src.category} · {src.latencyMs}ms</p>
                </div>
                <StatusBadge status={src.freshness} />
              </div>
            ))}
          </div>
        </Panel>

        {/* Recent Alerts */}
        <Panel title="Recent Alerts" className="lg:col-span-1">
          <div className="space-y-2">
            {mockAlerts.map((alert) => (
              <div key={alert.id} className={cn(
                'p-2.5 rounded border text-xs',
                alert.severity === 'critical' ? 'border-danger/30 bg-danger/5' :
                  alert.severity === 'warning' ? 'border-warning/30 bg-warning/5' :
                    'border-info/30 bg-info/5',
              )}>
                <div className="flex items-start gap-2">
                  {alert.severity === 'critical' ? <XCircle className="h-3.5 w-3.5 text-danger shrink-0 mt-0.5" /> :
                    alert.severity === 'warning' ? <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" /> :
                      <CheckCircle className="h-3.5 w-3.5 text-info shrink-0 mt-0.5" />}
                  <div>
                    <p className="font-mono font-medium text-foreground">{alert.title}</p>
                    <p className="font-mono text-muted-foreground mt-0.5">{alert.detail}</p>
                    <p className="font-mono text-muted-foreground mt-1 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatTimeCN(alert.timestamp)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* Recent Sessions */}
      <Panel title="Recent Sessions">
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="text-muted-foreground border-b border-border">
                <th className="text-left py-2 pr-4">Session</th>
                <th className="text-left py-2 pr-4">Symbol</th>
                <th className="text-left py-2 pr-4">Status</th>
                <th className="text-left py-2 pr-4">Action</th>
                <th className="text-right py-2 pr-4">PnL</th>
                <th className="text-left py-2">Time</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((sess) => (
                <tr key={sess.id} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                  <td className="py-2 pr-4 text-primary">{sess.id}</td>
                  <td className="py-2 pr-4 text-foreground font-semibold">{sess.symbol}</td>
                  <td className="py-2 pr-4"><StatusBadge status={sess.status} /></td>
                  <td className="py-2 pr-4">{sess.trade?.action || 'HOLD'}</td>
                  <td className={cn('py-2 pr-4 text-right', sess.trade?.pnl && sess.trade.pnl > 0 ? 'text-success' : sess.trade?.pnl && sess.trade.pnl < 0 ? 'text-danger' : 'text-muted-foreground')}>
                    {sess.trade?.pnl ? `$${sess.trade.pnl.toFixed(2)}` : '—'}
                  </td>
                  <td className="py-2 text-muted-foreground">{formatTimeCN(sess.startTime)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
