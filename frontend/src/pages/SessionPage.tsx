import { mockSessions } from '@/data/mock';
import { StatusBadge, Panel } from '@/components/shared/StatusBadge';
import { cn } from '@/lib/utils';
import { formatDateTimeCN, formatTimeCN } from '@/lib/time';
import { useState, useEffect } from 'react';
import { ChevronRight, Download, FileSearch, Loader2 } from 'lucide-react';
import type { Session, TradeAction, AgentRole, AgentMessage } from '@/types';
import { fetchSessions, fetchSessionDetail } from '@/data/api';

const AGENT_SEATS: { role: AgentRole; x: number; y: number; label: string }[] = [
  { role: 'market', x: 16, y: 16, label: 'MKT' },
  { role: 'macro', x: 34, y: 16, label: 'MAC' },
  { role: 'sentiment', x: 16, y: 34, label: 'SNT' },
  { role: 'onchain', x: 34, y: 34, label: 'OCH' },
  { role: 'analyst', x: 66, y: 18, label: 'ANA' },
  { role: 'bull_strategist', x: 58, y: 34, label: 'BUL' },
  { role: 'bear_strategist', x: 78, y: 34, label: 'BER' },
  { role: 'portfolio_manager', x: 18, y: 66, label: 'PM' },
  { role: 'reviewer', x: 34, y: 82, label: 'REV' },
  { role: 'executor', x: 66, y: 66, label: 'EXE' },
  { role: 'reflector', x: 82, y: 82, label: 'REF' },
];

const PIPELINE_EDGES: [AgentRole, AgentRole][] = [
  ['market', 'analyst'],
  ['macro', 'analyst'],
  ['onchain', 'analyst'],
  ['sentiment', 'analyst'],
  ['analyst', 'bull_strategist'],
  ['analyst', 'bear_strategist'],
  ['bull_strategist', 'portfolio_manager'],
  ['bear_strategist', 'portfolio_manager'],
  ['portfolio_manager', 'reviewer'],
  ['reviewer', 'executor'],
  ['executor', 'reflector'],
];

function getSeat(role: AgentRole) {
  return AGENT_SEATS.find((s) => s.role === role) || AGENT_SEATS[0];
}

function DialogueRoundtable({ messages }: { messages: AgentMessage[] }) {
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const sortedMessages = [...(messages || [])].sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp));
  const roleCounts: Record<string, number> = {};
  sortedMessages.forEach((m) => {
    roleCounts[m.agentRole] = (roleCounts[m.agentRole] || 0) + 1;
  });
  const upstreamByRole: Record<AgentRole, AgentRole[]> = {
    market: [],
    macro: [],
    sentiment: [],
    onchain: [],
    analyst: [],
    bull_strategist: [],
    bear_strategist: [],
    portfolio_manager: [],
    reviewer: [],
    executor: [],
    reflector: [],
  };
  PIPELINE_EDGES.forEach(([from, to]) => {
    upstreamByRole[to].push(from);
  });

  const pairTotals: Record<string, number> = {};
  const baseEdges: Array<{ fromRole: AgentRole; toRole: AgentRole; msg: AgentMessage; idx: number; key: string }> = [];
  sortedMessages.forEach((msg, idx) => {
    const upstreamRoles = upstreamByRole[msg.agentRole] || [];
    upstreamRoles.forEach((fromRole) => {
      const latestUpstreamIdx = sortedMessages
        .slice(0, idx)
        .map((m, i) => ({ m, i }))
        .reverse()
        .find((x) => x.m.agentRole === fromRole)?.i;
      if (latestUpstreamIdx === undefined) return;
      const key = `${fromRole}->${msg.agentRole}`;
      pairTotals[key] = (pairTotals[key] || 0) + 1;
      baseEdges.push({ fromRole, toRole: msg.agentRole, msg, idx, key });
    });
  });
  const pairSeen: Record<string, number> = {};
  const edges = baseEdges.map((e) => {
    pairSeen[e.key] = (pairSeen[e.key] || 0) + 1;
    return { ...e, seen: pairSeen[e.key], total: pairTotals[e.key] };
  });

  if (!sortedMessages.length) {
    return <p className="text-xs font-mono text-muted-foreground">No dialogue logs in this session.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="relative w-full rounded border border-border/60 bg-secondary/10" style={{ paddingBottom: '72%' }}>
        <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
          {edges.map((e) => {
            const p1 = getSeat(e.fromRole);
            const p2 = getSeat(e.toRole);
            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const horizontal = Math.abs(dx) >= Math.abs(dy);
            const lane = e.seen - (e.total + 1) / 2;
            const laneOffset = lane * 2.2;
            const c1x = horizontal ? p1.x + dx * 0.35 : p1.x + laneOffset;
            const c1y = horizontal ? p1.y + laneOffset : p1.y + dy * 0.35;
            const c2x = horizontal ? p1.x + dx * 0.65 : p2.x + laneOffset;
            const c2y = horizontal ? p2.y + laneOffset : p1.y + dy * 0.65;
            const d = `M ${p1.x} ${p1.y} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
            const isActive = activeIdx === e.idx;
            return (
              <g key={`${e.key}-${e.idx}`}>
                <path
                  d={d}
                  fill="none"
                  stroke={isActive ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))'}
                  strokeWidth={isActive ? 0.7 : 0.35}
                  strokeOpacity={isActive ? 0.95 : 0.3}
                  className="cursor-pointer transition-all pointer-events-auto"
                  onClick={() => setActiveIdx(e.idx)}
                />
              </g>
            );
          })}
        </svg>
        {AGENT_SEATS.map((seat) => (
          <div
            key={seat.role}
            className={cn(
              'absolute w-10 h-10 -translate-x-1/2 -translate-y-1/2 rounded-full border text-[9px] font-mono flex flex-col items-center justify-center bg-card/95',
              roleCounts[seat.role] ? 'border-primary/40 text-primary' : 'border-border/60 text-muted-foreground'
            )}
            style={{ left: `${seat.x}%`, top: `${seat.y}%` }}
          >
            <span>{seat.label}</span>
            <span className="text-[8px]">{roleCounts[seat.role] || 0}</span>
          </div>
        ))}
      </div>

      <div className="max-h-56 overflow-y-auto rounded border border-border/40 bg-background/30">
        {edges.map((e) => (
          <button
            key={`row-${e.idx}`}
            onClick={() => setActiveIdx(e.idx)}
            className={cn(
              'w-full text-left px-2.5 py-2 border-b border-border/30 last:border-0 text-[11px] font-mono',
              activeIdx === e.idx ? 'bg-primary/10' : 'hover:bg-secondary/30'
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-muted-foreground">#{e.idx + 1}</span>
              <span className="text-muted-foreground">{formatTimeCN(e.msg.timestamp)}</span>
            </div>
            <div className="text-foreground mt-0.5">
              {e.fromRole} → {e.toRole} · {e.msg.messageType}
            </div>
            <p className="text-muted-foreground mt-1 line-clamp-2">{e.msg.content}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

function SessionDetail({ session }: { session: Session }) {
  const [expandedSection, setExpandedSection] = useState<string | null>('trade');

  const sections = [
    { id: 'input', label: 'Data Input', count: session.messages?.filter(m => ['market', 'macro', 'onchain', 'sentiment'].includes(m.agentRole)).length || 0 },
    { id: 'dialogue', label: 'Agent Dialogue', count: session.messages?.length || 0 },
    { id: 'risk', label: 'Risk Gates', count: session.riskGates.length },
    { id: 'trade', label: 'Trade Execution', count: session.trade ? 1 : 0 },
    { id: 'reflection', label: 'Reflection', count: session.reflection ? 1 : 0 },
  ];

  return (
    <div className="space-y-3">
      {/* Pipeline breadcrumb */}
      <div className="flex items-center gap-1 text-xs font-mono text-muted-foreground flex-wrap">
        {sections.map((s, i) => (
          <button
            key={s.id}
            onClick={() => setExpandedSection(expandedSection === s.id ? null : s.id)}
            className={cn(
              'flex items-center gap-1 px-2 py-1 rounded transition-colors',
              expandedSection === s.id ? 'bg-primary/10 text-primary' : 'hover:text-foreground',
            )}
          >
            {s.label} ({s.count})
            {i < sections.length - 1 && <ChevronRight className="h-3 w-3 text-muted-foreground" />}
          </button>
        ))}
      </div>

      {/* Input */}
      {expandedSection === 'input' && (
        <Panel title="Data Inputs">
          <div className="space-y-2">
            {session.messages
              ?.filter(m => ['market', 'macro', 'onchain', 'sentiment'].includes(m.agentRole))
              .map(m => (
                <div key={m.id} className="p-2 rounded bg-secondary/30 border border-border/50 text-xs font-mono">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-foreground font-medium">{m.agentName}</span>
                    <StatusBadge status={m.messageType} />
                  </div>
                  <div className="text-muted-foreground whitespace-pre-wrap">{m.content}</div>
                </div>
              ))}
          </div>
        </Panel>
      )}

      {/* Dialogue summary */}
      {expandedSection === 'dialogue' && (
        <Panel title="Agent Dialogue">
          <DialogueRoundtable messages={session.messages || []} />
        </Panel>
      )}

      {/* Risk */}
      {expandedSection === 'risk' && (
        <Panel title="Risk Gates">
          <div className="space-y-2">
            {session.riskGates?.map((gate, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded bg-secondary/30 border border-border/50 text-xs font-mono">
                <div>
                  <span className="text-foreground font-medium">{gate.name}</span>
                  <span className="text-muted-foreground ml-2">({gate.type})</span>
                  <p className="text-muted-foreground mt-0.5">{gate.detail}</p>
                </div>
                <StatusBadge status={gate.status} />
              </div>
            ))}
            {(!session.riskGates || session.riskGates.length === 0) && (
              <p className="text-xs font-mono text-muted-foreground">No risk gates triggered or recorded.</p>
            )}
          </div>
        </Panel>
      )}

      {/* Trade */}
      {expandedSection === 'trade' && (
        <Panel title="Trade Execution">
          {session.trade ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <tbody>
                  {[
                    ['Action', session.trade.action],
                    ['Order Type', session.trade.orderType],
                    ['Trigger', session.trade.triggerCondition],
                    ['Quantity', session.trade.quantity],
                    ['Entry Price', `$${session.trade.entryPrice.toLocaleString()}`],
                    ['Executed Price', session.trade.executedPrice ? `$${session.trade.executedPrice.toLocaleString()}` : '—'],
                    ['Slippage', session.trade.slippageBps ? `${session.trade.slippageBps}bps` : '—'],
                    ['Fee', `$${session.trade.fee.toFixed(2)}`],
                    ['PnL', session.trade.pnl !== null ? `$${session.trade.pnl.toFixed(2)}` : '—'],
                    ['Status', null],
                    ['Reject Code', session.trade.rejectCode || 'None'],
                    ['New Balance', `$${session.trade.newBalance.toLocaleString()}`],
                  ].map(([key, val]) => (
                    <tr key={key as string} className="border-b border-border/30">
                      <td className="py-1.5 pr-4 text-muted-foreground">{key}</td>
                      <td className={cn('py-1.5',
                        key === 'PnL' && session.trade?.pnl && session.trade.pnl > 0 ? 'text-success' :
                          key === 'PnL' && session.trade?.pnl && session.trade.pnl < 0 ? 'text-danger' : 'text-foreground',
                      )}>
                        {key === 'Status' ? <StatusBadge status={session.trade!.status} /> : val}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs font-mono text-muted-foreground">No trade executed (HOLD / REJECTED)</p>
          )}
        </Panel>
      )}

      {/* Reflection */}
      {expandedSection === 'reflection' && (
        <Panel title="Reflection">
          {session.reflection ? (
            <div className="space-y-3 text-xs font-mono">
              <div>
                <p className="text-success font-medium mb-1">What Went Right</p>
                <ul className="space-y-1">
                  {session.reflection.whatWentRight.map((item, i) => (
                    <li key={i} className="text-muted-foreground pl-3 border-l-2 border-success/30">{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-danger font-medium mb-1">What Went Wrong</p>
                <ul className="space-y-1">
                  {session.reflection.whatWentWrong.map((item, i) => (
                    <li key={i} className="text-muted-foreground pl-3 border-l-2 border-danger/30">{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-primary font-medium mb-1">Improvements</p>
                <ul className="space-y-1">
                  {session.reflection.improvements.map((item, i) => (
                    <li key={i} className="text-muted-foreground pl-3 border-l-2 border-primary/30">{item}</li>
                  ))}
                </ul>
              </div>
              {session.reflection.failureMode && (
                <div className="p-2 rounded bg-danger/5 border border-danger/20">
                  <span className="text-danger">Failure Mode: {session.reflection.failureMode}</span>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs font-mono text-muted-foreground">No reflection data for this session</p>
          )}
        </Panel>
      )}
    </div>
  );
}

export default function SessionPage() {
  const [sessions, setSessions] = useState<Session[]>(mockSessions);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [filterSymbol, setFilterSymbol] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterSessionId, setFilterSessionId] = useState<string>('');
  const [sessionLogsMap, setSessionLogsMap] = useState<Record<string, any[]>>({});

  useEffect(() => {
    fetchSessions().then(history => {
      const mapped = history.map((h: any) => ({
        id: h.id,
        symbol: h.symbol,
        status: h.status,
        startTime: h.start_time,
        endTime: h.end_time || h.start_time,
        trade: h.action ? {
          action: h.action as TradeAction,
          orderType: 'MARKET' as const,
          triggerCondition: 'N/A',
          quantity: 0,
          entryPrice: 0,
          executedPrice: 0,
          slippageBps: 0,
          fee: 0,
          pnl: 0,
          status: 'FILLED' as const,
          rejectCode: null,
          newBalance: 0,
          timestamp: h.end_time || h.start_time,
        } as any : null,
        orchestrationConfig: mockSessions[0].orchestrationConfig,
        revisionRounds: [],
        messages: [],
        debate: null,
        riskGates: [],
        reflection: null,
      }));
      setSessions(mapped);
    }).catch(console.error);
  }, []);

  const handleSelectSession = async (sess: Session) => {
    setSelectedSession(sess);
    setLoadingDetail(true);
    try {
      const detail = await fetchSessionDetail(sess.id);
      // Map logs to messages
      const messages = (detail.logs || []).map((l: any) => {
        let parsedContent = l.content;
        try {
          if (l.artifact && Object.keys(l.artifact).length > 0) {
            parsedContent += '\n\n[Artifact Data]:\n' + JSON.stringify(l.artifact, null, 2);
          }
        } catch (e) {}

        return {
          id: l.id,
          sessionId: sess.id,
          agentRole: l.agent_id,
          agentName: l.agent_id.toUpperCase(),
          messageType: l.type === 'error' ? 'error' : (l.type === 'warning' ? 'warning' : 'output'),
          content: parsedContent,
          timestamp: l.timestamp,
          confidence: l.artifact?.confidence || undefined,
        };
      });
      
      const reflectionLog = (detail.logs || []).find((l: any) => l.agent_id === 'reflector' && l.artifact?.type === 'REFLECTION');
      let reflection = null;
      if (reflectionLog) {
        try {
          const content = JSON.parse(reflectionLog.artifact.content);
          reflection = {
            id: reflectionLog.id,
            sessionId: sess.id,
            whatWentRight: content.what_went_right || [],
            whatWentWrong: content.what_went_wrong || [],
            improvements: content.improvements || [],
            failureMode: content.failure_mode || null,
            ruleChanges: [],
            timestamp: reflectionLog.timestamp,
          };
        } catch (e) {}
      }

      setSelectedSession(prev => prev ? {
        ...prev,
        messages,
        reflection,
        trade: detail.trade_plan ? {
          action: detail.trade_plan.action as TradeAction,
          orderType: 'MARKET',
          triggerCondition: 'N/A',
          quantity: detail.trade_plan.quantity || 0,
          entryPrice: detail.trade_plan.entry_price || 0,
          executedPrice: 0,
          slippageBps: 0,
          fee: 0,
          pnl: 0,
          status: 'FILLED' as const,
          rejectCode: null,
          newBalance: 0,
          timestamp: sess.endTime || '',
        } as any : prev.trade,
      } : null);
      setSessionLogsMap((prev) => ({ ...prev, [sess.id]: detail.logs || [] }));
    } catch (err) {
      console.error("Failed to fetch session detail:", err);
      // Fallback to minimal session display on error to avoid infinite loading state
      setSelectedSession(sess);
    } finally {
      setLoadingDetail(false);
    }
  };

  const symbols = ['all', ...Array.from(new Set(sessions.map(s => s.symbol)))];
  const statuses = ['all', 'COMPLETED', 'REJECTED', 'FAILED', 'RUNNING'];

  const filtered = sessions.filter(s =>
    (!filterSessionId.trim() || s.id.toLowerCase().includes(filterSessionId.trim().toLowerCase())) &&
    (filterSymbol === 'all' || s.symbol === filterSymbol) &&
    (filterStatus === 'all' || s.status === filterStatus)
  );

  const handleDownloadSessionLogs = () => {
    if (!selectedSession) return;
    const rawLogs = sessionLogsMap[selectedSession.id] || [];
    const payload = {
      session_id: selectedSession.id,
      symbol: selectedSession.symbol,
      status: selectedSession.status,
      start_time: selectedSession.startTime,
      end_time: selectedSession.endTime,
      logs: rawLogs,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `session-${selectedSession.id}-logs.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 animate-slide-in">
      <div>
        <h1 className="text-xl font-mono font-bold text-foreground">Session History</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">Browse and audit historical trading sessions</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-mono text-muted-foreground">Session ID:</span>
          <input
            value={filterSessionId}
            onChange={(e) => setFilterSessionId(e.target.value)}
            placeholder="search session id"
            className="h-8 w-56 rounded border border-border bg-background px-2 text-xs font-mono text-foreground placeholder:text-muted-foreground outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-mono text-muted-foreground">Symbol:</span>
          {symbols.map(sym => (
            <button key={sym} onClick={() => setFilterSymbol(sym)}
              className={cn('px-2 py-1 text-xs font-mono rounded border transition-colors',
                filterSymbol === sym ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground')}>
              {sym.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-mono text-muted-foreground">Status:</span>
          {statuses.map(st => (
            <button key={st} onClick={() => setFilterStatus(st)}
              className={cn('px-2 py-1 text-xs font-mono rounded border transition-colors',
                filterStatus === st ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground')}>
              {st}
            </button>
          ))}
        </div>
        <button
          onClick={handleDownloadSessionLogs}
          disabled={!selectedSession}
          className="ml-auto flex items-center gap-1.5 h-8 px-2.5 rounded border border-border text-xs font-mono text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Download className="h-3.5 w-3.5" />
          Download Logs
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Session List */}
        <Panel title="Sessions" className="lg:col-span-1">
          <div className="space-y-1">
            {filtered.map(sess => (
              <button
                key={sess.id}
                onClick={() => handleSelectSession(sess)}
                className={cn(
                  'w-full text-left p-2.5 rounded border text-xs font-mono transition-colors',
                  selectedSession?.id === sess.id
                    ? 'border-primary bg-primary/10'
                    : 'border-border/50 bg-secondary/20 hover:bg-secondary/40',
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-primary">{sess.id}</span>
                  <StatusBadge status={sess.status} />
                </div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-foreground font-semibold">{sess.symbol}</span>
                  <span className="text-muted-foreground">{sess.trade?.action || 'HOLD'}</span>
                </div>
                <span className="text-muted-foreground text-[10px]">{formatDateTimeCN(sess.startTime)}</span>
              </button>
            ))}
          </div>
        </Panel>

        {/* Detail */}
        <div className="lg:col-span-3">
          {loadingDetail ? (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <Loader2 className="h-8 w-8 mb-2 animate-spin opacity-40" />
              <p className="text-sm font-mono">Loading session details...</p>
            </div>
          ) : selectedSession ? (
            <SessionDetail session={selectedSession} />
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <FileSearch className="h-8 w-8 mb-2 opacity-40" />
              <p className="text-sm font-mono">Select a session to inspect</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
