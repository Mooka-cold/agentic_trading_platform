import { mockSessions, mockOrchConfig, mockAgents } from '@/data/mock';
import { Panel, StatusBadge, agentColorMap } from '@/components/shared/StatusBadge';
import { cn } from '@/lib/utils';
import { formatTimeCN } from '@/lib/time';
import { useState, useEffect } from 'react';
import type { AgentRole, Session } from '@/types';
import { fetchSessions, fetchSessionDetail } from '@/data/api';
import { Loader2 } from 'lucide-react';

// ─── Orchestration Graph Node ──────────────────────────────

const graphNodes: { role: AgentRole; label: string; x: number; y: number; layer: string }[] = [
  // Input layer
  { role: 'market', label: 'Market', x: 80, y: 40, layer: 'input' },
  { role: 'macro', label: 'Macro', x: 230, y: 40, layer: 'input' },
  { role: 'onchain', label: 'Onchain', x: 380, y: 40, layer: 'input' },
  { role: 'sentiment', label: 'Sentiment', x: 530, y: 40, layer: 'input' },
  // Processing
  { role: 'analyst', label: 'Analyst', x: 305, y: 130, layer: 'process' },
  // Debate
  { role: 'bull_strategist', label: 'Bull', x: 180, y: 220, layer: 'debate' },
  { role: 'bear_strategist', label: 'Bear', x: 430, y: 220, layer: 'debate' },
  // Decision
  { role: 'portfolio_manager', label: 'PM', x: 305, y: 310, layer: 'decision' },
  // Review
  { role: 'reviewer', label: 'Reviewer', x: 305, y: 390, layer: 'review' },
  // Execution
  { role: 'executor', label: 'Executor', x: 305, y: 470, layer: 'execute' },
  // Reflection
  { role: 'reflector', label: 'Reflector', x: 305, y: 550, layer: 'reflect' },
];

const graphEdges = [
  ['market', 'analyst'], ['macro', 'analyst'], ['onchain', 'analyst'], ['sentiment', 'analyst'],
  ['analyst', 'bull_strategist'], ['analyst', 'bear_strategist'],
  ['bull_strategist', 'portfolio_manager'], ['bear_strategist', 'portfolio_manager'],
  ['portfolio_manager', 'reviewer'],
  ['reviewer', 'executor'],
  ['executor', 'reflector'],
];

const nodeColorFill: Record<string, string> = {
  market: '#3b98d4', macro: '#9060c0', onchain: '#3da85c', sentiment: '#d44a8a',
  analyst: '#d4a030', bull_strategist: '#3cb371', bear_strategist: '#d44a4a',
  portfolio_manager: '#30b8c4', reviewer: '#9060c0', executor: '#d48c30', reflector: '#4488cc',
};

function OrchestrationGraph({ activeNode }: { activeNode: AgentRole | null }) {
  return (
    <svg viewBox="0 0 620 600" className="w-full max-w-2xl mx-auto" style={{ height: 'auto' }}>
      {/* Grid background */}
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="hsl(220 15% 18%)" strokeWidth="0.5" opacity="0.3" />
        </pattern>
      </defs>
      <rect width="620" height="600" fill="url(#grid)" />

      {/* Edges */}
      {graphEdges.map(([from, to], i) => {
        const fromNode = graphNodes.find(n => n.role === from)!;
        const toNode = graphNodes.find(n => n.role === to)!;
        const isActive = activeNode === from || activeNode === to;
        return (
          <line
            key={i}
            x1={fromNode.x} y1={fromNode.y + 18}
            x2={toNode.x} y2={toNode.y - 18}
            stroke={isActive ? 'hsl(185 70% 50%)' : 'hsl(220 15% 25%)'}
            strokeWidth={isActive ? 2 : 1}
            opacity={isActive ? 1 : 0.5}
          />
        );
      })}

      {/* Revision round arc (PM -> Analyst) */}
      <path
        d="M 265 310 C 100 310 100 130 265 130"
        fill="none"
        stroke="hsl(38 92% 50%)"
        strokeWidth="1"
        strokeDasharray="4 4"
        opacity="0.5"
      />
      <text x="60" y="225" fill="hsl(38 92% 50%)" fontSize="9" fontFamily="monospace" opacity="0.7">revision</text>

      {/* Nodes */}
      {graphNodes.map((node) => {
        const isActive = activeNode === node.role;
        const fill = nodeColorFill[node.role] || '#666';
        return (
          <g key={node.role}>
            {isActive && (
              <circle cx={node.x} cy={node.y} r="26" fill={fill} opacity="0.15" />
            )}
            <circle
              cx={node.x} cy={node.y} r="18"
              fill={`${fill}22`}
              stroke={fill}
              strokeWidth={isActive ? 2 : 1}
              opacity={isActive ? 1 : 0.7}
            />
            <text
              x={node.x} y={node.y + 4}
              textAnchor="middle"
              fill={fill}
              fontSize="9"
              fontFamily="monospace"
              fontWeight={isActive ? 700 : 400}
            >
              {node.label}
            </text>
          </g>
        );
      })}

      {/* Layer labels */}
      {[
        { y: 40, label: 'DATA INPUT' },
        { y: 130, label: 'ANALYSIS' },
        { y: 220, label: 'DEBATE' },
        { y: 310, label: 'DECISION' },
        { y: 390, label: 'REVIEW' },
        { y: 470, label: 'EXECUTION' },
        { y: 550, label: 'REFLECTION' },
      ].map(({ y, label }) => (
        <text key={label} x="608" y={y + 4} textAnchor="end" fill="hsl(215 15% 35%)" fontSize="8" fontFamily="monospace">
          {label}
        </text>
      ))}
    </svg>
  );
}

export default function OrchestrationPage() {
  const [sessions, setSessions] = useState<Session[]>(mockSessions.slice(0, 5));
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(false);
  const config = mockOrchConfig; // Still using mock config for now

  useEffect(() => {
    fetchSessions().then(history => {
      const mapped = history.slice(0, 5).map((h: any) => ({
        id: h.id,
        symbol: h.symbol,
        status: h.status,
        startTime: h.start_time,
        endTime: h.end_time || h.start_time,
        trade: h.action ? { action: h.action, pnl: 0 } : null,
        orchestrationConfig: mockSessions[0].orchestrationConfig,
        revisionRounds: [],
        messages: [],
        debate: null,
        riskGates: [],
        reflection: null,
      }));
      setSessions(mapped);
      if (mapped.length > 0) {
        handleSelectSession(mapped[0]);
      }
    }).catch(console.error);
  }, []);

  const handleSelectSession = async (sess: Session) => {
    setSelectedSession(sess);
    setLoading(true);
    try {
      const detail = await fetchSessionDetail(sess.id);
      
      const messages = detail.logs.map((l: any) => ({
        id: l.id,
        sessionId: sess.id,
        agentRole: l.agent_id,
        agentName: l.agent_id.toUpperCase(),
        messageType: l.type === 'error' ? 'error' : (l.type === 'warning' ? 'warning' : 'output'),
        content: l.content,
        timestamp: l.timestamp,
        confidence: l.artifact?.confidence || undefined,
        reasoning: l.artifact?.reasoning || undefined,
      }));

      setSelectedSession(prev => prev ? {
        ...prev,
        messages,
      } : null);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!selectedSession) {
    return <div className="p-8 text-center text-muted-foreground"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2"/> Loading orchestration state...</div>;
  }

  // Determine active node based on session
  const lastMsg = selectedSession.messages[selectedSession.messages.length - 1];
  const activeNode = selectedSession.status === 'RUNNING' ? lastMsg?.agentRole : null;

  return (
    <div className="space-y-6 animate-slide-in">
      <div>
        <h1 className="text-xl font-mono font-bold text-foreground">Orchestration Studio</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">Agent pipeline visualization & configuration</p>
      </div>

      {/* Session selector */}
      <div className="flex items-center gap-2 flex-wrap">
        {sessions.map((sess) => (
          <button
            key={sess.id}
            onClick={() => handleSelectSession(sess)}
            className={cn(
              'px-3 py-1.5 text-xs font-mono rounded border transition-colors',
              selectedSession.id === sess.id
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border bg-card text-muted-foreground hover:text-foreground',
            )}
          >
            {sess.id} · {sess.symbol}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Graph */}
        <Panel title="Pipeline Graph" className="lg:col-span-2">
          <OrchestrationGraph activeNode={activeNode} />
        </Panel>

        {/* Config */}
        <div className="space-y-4">
          <Panel title="Orchestration Config">
            <div className="space-y-2 text-xs font-mono">
              {[
                ['max_revision_rounds', config.max_revision_rounds],
                ['data_routing_policy', config.data_routing_policy],
                ['cross_examiner', config.cross_examiner_enabled ? 'enabled' : 'disabled'],
                ['hold_bias', config.hold_bias],
                ['risk_policy', config.risk_reduction_policy],
                ['max_slippage', `${config.execution_constraints.max_slippage_bps}bps`],
                ['max_position', `${config.execution_constraints.max_position_pct}%`],
                ['twap_duration', `${config.execution_constraints.twap_duration_min}min`],
              ].map(([key, val]) => (
                <div key={key as string} className="flex justify-between py-1 border-b border-border/50">
                  <span className="text-muted-foreground">{key as string}</span>
                  <span className="text-foreground">{String(val)}</span>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Revision Rounds">
            {selectedSession.revisionRounds.length === 0 ? (
              <p className="text-xs font-mono text-muted-foreground">No revision rounds</p>
            ) : (
              <div className="space-y-2">
                {selectedSession.revisionRounds.map((rev) => (
                  <div key={rev.round} className="p-2 rounded border border-warning/20 bg-warning/5 text-xs font-mono">
                    <div className="flex items-center gap-2 text-warning font-medium">
                      <span>Round {rev.round}</span>
                      <span className="text-muted-foreground">·</span>
                      <span className="text-muted-foreground">{formatTimeCN(rev.timestamp)}</span>
                    </div>
                    <p className="text-muted-foreground mt-1">Trigger: {rev.trigger}</p>
                    <p className="text-foreground mt-0.5">Change: {rev.changes}</p>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Risk Gates">
            <div className="space-y-1.5">
              {selectedSession.riskGates.map((gate, i) => (
                <div key={i} className="flex items-center justify-between py-1 border-b border-border/50 last:border-0">
                  <div>
                    <p className="text-xs font-mono text-foreground">{gate.name}</p>
                    <p className="text-[10px] font-mono text-muted-foreground">{gate.type}</p>
                  </div>
                  <StatusBadge status={gate.status} />
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
