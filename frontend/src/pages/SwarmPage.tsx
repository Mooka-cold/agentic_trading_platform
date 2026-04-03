import { mockSessions, mockAgents } from '@/data/mock';
import { StatusBadge, Panel, ConfidenceBar, agentColorMap } from '@/components/shared/StatusBadge';
import { cn } from '@/lib/utils';
import { useState, useMemo, useEffect } from 'react';
import type { AgentMessage, Session, AgentRole } from '@/types';
import { Scale, Swords, ChevronDown, ChevronUp, MessageSquare, ArrowRight, CheckCircle2, XCircle, AlertTriangle, Loader2, Play, Square, RefreshCw } from 'lucide-react';
import { fetchSessions, fetchSessionDetail, fetchWorkflowRunnerStatus, runWorkflow, stopWorkflow } from '@/data/api';

// ─── Agent seat definitions ────────────────────────────────

const AGENT_SEATS: { role: AgentRole; label: string; shortLabel: string; x: number; y: number; team: string }[] = [
  { role: 'market', label: 'Market Scanner', shortLabel: 'MKT', x: 16, y: 16, team: 'Data Team' },
  { role: 'macro', label: 'Macro Analyst', shortLabel: 'MAC', x: 34, y: 16, team: 'Data Team' },
  { role: 'sentiment', label: 'Sentiment Gauge', shortLabel: 'SNT', x: 16, y: 34, team: 'Data Team' },
  { role: 'onchain', label: 'Onchain Monitor', shortLabel: 'OCH', x: 34, y: 34, team: 'Data Team' },
  { role: 'analyst', label: 'Chief Analyst', shortLabel: 'ANA', x: 66, y: 18, team: 'Strategy Team' },
  { role: 'bull_strategist', label: 'Bull Strategist', shortLabel: 'BULL', x: 58, y: 34, team: 'Strategy Team' },
  { role: 'bear_strategist', label: 'Bear Strategist', shortLabel: 'BEAR', x: 78, y: 34, team: 'Strategy Team' },
  { role: 'portfolio_manager', label: 'Portfolio Manager', shortLabel: 'PM', x: 18, y: 66, team: 'Risk Team' },
  { role: 'reviewer', label: 'Risk Reviewer', shortLabel: 'REV', x: 34, y: 82, team: 'Risk Team' },
  { role: 'executor', label: 'Trade Executor', shortLabel: 'EXE', x: 66, y: 66, team: 'Execution Team' },
  { role: 'reflector', label: 'Reflector', shortLabel: 'REF', x: 82, y: 82, team: 'Execution Team' },
];

const TEAM_ZONES = [
  { team: 'Data Team', x: 25, y: 25, w: 44, h: 42 },
  { team: 'Strategy Team', x: 75, y: 25, w: 44, h: 42 },
  { team: 'Risk Team', x: 25, y: 75, w: 44, h: 42 },
  { team: 'Execution Team', x: 75, y: 75, w: 44, h: 42 },
];

// Communication edges: from → to, derived from the pipeline
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

const agentTextColor: Record<string, string> = {
  market: 'text-agent-market', macro: 'text-agent-macro', onchain: 'text-agent-onchain',
  sentiment: 'text-agent-sentiment', analyst: 'text-agent-analyst',
  bull_strategist: 'text-agent-bull', bear_strategist: 'text-agent-bear',
  portfolio_manager: 'text-agent-pm', reviewer: 'text-agent-reviewer',
  executor: 'text-agent-executor', reflector: 'text-agent-reflector',
};

// ─── Helpers ───────────────────────────────────────────────

function getAgentPos(role: AgentRole) {
  const seat = AGENT_SEATS.find(s => s.role === role)!;
  return { x: seat.x, y: seat.y };
}

function getLastMessage(session: Session, role: AgentRole): AgentMessage | undefined {
  const msgs = session.messages.filter(m => m.agentRole === role);
  return msgs.length > 0 ? msgs[msgs.length - 1] : undefined;
}

function getActiveEdges(session: Session): [AgentRole, AgentRole][] {
  const activeRoles = new Set(session.messages.map(m => m.agentRole));
  return PIPELINE_EDGES.filter(([from, to]) => activeRoles.has(from) && activeRoles.has(to));
}

function getPhaseStyle(msg?: AgentMessage) {
  if (!msg) return { ring: 'ring-border/50', bg: 'bg-card', pulse: false };
  if (msg.messageType === 'error') return { ring: 'ring-danger', bg: 'bg-danger/10', pulse: false };
  if (msg.messageType === 'warning') return { ring: 'ring-warning', bg: 'bg-warning/10', pulse: true };
  if (msg.messageType === 'think') return { ring: 'ring-primary', bg: 'bg-primary/10', pulse: true };
  return { ring: 'ring-success', bg: 'bg-success/5', pulse: false };
}

// ─── Pixel Art Agent Sprites (8x8 grid rendered as SVG) ────

const SPRITE_SIZE = 12; // 12x12 grid

const PIXEL_SPRITES: Record<string, string[]> = {
  // . = transparent, ^ = skin, o = eye, # = body, x = accent, + = accessory, ~ = special, m = mouth, h = hair
  // Market Scanner: antenna + radar dish, scanning pose with arm out
  market: [
    '....+~+.....',
    '.....++.....',
    '...h^^^^h...',
    '...^^^^^^...',
    '...^oo^^m...',
    '...^^^^^^...',
    '..~.#xx#.~..',
    '...~#xx#~...',
    '....####....',
    '....####....',
    '...#....#...',
    '...#....#...',
  ],
  // Macro Analyst: top hat + monocle, distinguished pose
  macro: [
    '...++++++...',
    '..++++++++..',
    '...^^^^^^...',
    '...^^^^^^...',
    '...~o.^o^...',
    '....^mm^....',
    '....#xx#....',
    '...######...',
    '....#xx#....',
    '....####....',
    '....#..#....',
    '...##..##...',
  ],
  // Onchain Monitor: headset + chain links on arms
  onchain: [
    '....~..~....',
    '...^^^^^^...',
    '..~^^^^^^~..',
    '...^oo^^....',
    '...^^mm^....',
    '....^^^^....',
    '+~..####..~+',
    '.+~.#xx#.~+.',
    '....####....',
    '....####....',
    '....#..#....',
    '....#..#....',
  ],
  // Sentiment Gauge: big smile + heart on chest, open arms
  sentiment: [
    '............',
    '...hh^^hh...',
    '...^^^^^^...',
    '...^oo^^....',
    '...^^mm^....',
    '....^^^^....',
    '..+.#++#.+..',
    '....#+x#....',
    '....####....',
    '....####....',
    '...#....#...',
    '...#....#...',
  ],
  // Chief Analyst: glasses + clipboard, thinking pose (hand on chin)
  analyst: [
    '............',
    '...^^^^^^...',
    '...^^^^^^...',
    '..~oo~~oo~..',
    '...^^mm^....',
    '....^^^^.+..',
    '....#xx#.+..',
    '...######+..',
    '....#xx#....',
    '....####....',
    '....#..#....',
    '...##..##...',
  ],
  // Bull Strategist: large horns + muscular build, fist raised
  bull_strategist: [
    '+...^^...+..',
    '.+.^^^^.+...',
    '..^^^^^^....',
    '...^oo^.....',
    '...^^m^.....',
    '....^^^^....',
    '..+.#xx#....',
    '.++.####....',
    '....#xx#....',
    '...######...',
    '....#..#....',
    '...##..##...',
  ],
  // Bear Strategist: round ears + heavy build, arms crossed
  bear_strategist: [
    '..++..++....',
    '.+++^^+++...',
    '...^^^^^^...',
    '...^oo^.....',
    '...^^m^.....',
    '....^^^^....',
    '...x####x...',
    '...x#xx#x...',
    '....####....',
    '...######...',
    '....#..#....',
    '...##..##...',
  ],
  // Portfolio Manager: necktie + suit jacket, confident stance
  portfolio_manager: [
    '............',
    '...^^^^^^...',
    '...^^^^^^...',
    '...^oo^^....',
    '...^^mm^....',
    '....^^^^....',
    '..xx#++#xx..',
    '..###+x###..',
    '....#+x#....',
    '....####....',
    '....#..#....',
    '...##..##...',
  ],
  // Risk Reviewer: shield + visor helmet
  reviewer: [
    '..~~~~~~~...',
    '..~^^^^^^...',
    '...^^^^^^...',
    '...^oo^^....',
    '...^^mm^....',
    '....^^^^....',
    '.++++####...',
    '.+xx+#xx#...',
    '.++++####...',
    '....####....',
    '....#..#....',
    '...##..##...',
  ],
  // Trade Executor: lightning bolt + speed lines, action pose
  executor: [
    '............',
    '...^^^^^^...',
    '...^^^^^^...',
    '...^oo^^....',
    '...^^mm^....',
    '....^^^^.~..',
    '....#xx#~~..',
    '...####.~...',
    '....#xx#.~..',
    '....####.~..',
    '...#..#.....',
    '..##...##...',
  ],
  // Reflector: halo + meditation pose (legs crossed)
  reflector: [
    '..~++++++~..',
    '...~....~...',
    '...^^^^^^...',
    '...^^^^^^...',
    '...^oo^^....',
    '...^^mm^....',
    '....#xx#....',
    '...######...',
    '....#xx#....',
    '....####....',
    '...##..##...',
    '..##....##..',
  ],
};

// HSL raw values for SVG fills (matching tailwind agent tokens)
const agentHslMap: Record<string, string> = {
  market: 'hsl(var(--agent-market))',
  macro: 'hsl(var(--agent-macro))',
  onchain: 'hsl(var(--agent-onchain))',
  sentiment: 'hsl(var(--agent-sentiment))',
  analyst: 'hsl(var(--agent-analyst))',
  bull_strategist: 'hsl(var(--agent-bull))',
  bear_strategist: 'hsl(var(--agent-bear))',
  portfolio_manager: 'hsl(var(--agent-pm))',
  reviewer: 'hsl(var(--agent-reviewer))',
  executor: 'hsl(var(--agent-executor))',
  reflector: 'hsl(var(--agent-reflector))',
};

function PixelSprite({ role, size = 40 }: { role: AgentRole; size?: number }) {
  const sprite = PIXEL_SPRITES[role] || PIXEL_SPRITES.market;
  const color = agentHslMap[role];
  const px = size / SPRITE_SIZE;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="pixelated">
      {sprite.map((row, y) =>
        row.split('').map((ch, x) => {
          if (ch === '.') return null;
          let fill = color;
          if (ch === '^') fill = 'hsl(var(--foreground))';        // skin/head
          if (ch === 'h') fill = 'hsl(var(--foreground) / 0.7)';  // hair
          if (ch === 'o') fill = 'hsl(var(--primary))';            // eyes
          if (ch === 'm') fill = 'hsl(var(--destructive))';        // mouth
          if (ch === 'x') fill = color;                             // accent
          if (ch === '#') fill = 'hsl(var(--muted-foreground))';   // body
          if (ch === '+') fill = color;                             // accessory
          if (ch === '~') fill = 'hsl(var(--primary))';            // special detail
          return (
            <rect key={`${x}-${y}`} x={x * px} y={y * px} width={px} height={px} fill={fill} />
          );
        })
      )}
    </svg>
  );
}

// ─── Agent Node Component ──────────────────────────────────

function AgentNode({ role, label, shortLabel, session, isSelected, onClick }: {
  role: AgentRole; label: string; shortLabel: string;
  session: Session; isSelected: boolean; onClick: () => void;
}) {
  const pos = getAgentPos(role);
  const lastMsg = getLastMessage(session, role);
  const { bg, pulse } = getPhaseStyle(lastMsg);
  const confidence = lastMsg?.confidence;

  return (
    <div
      className="absolute flex flex-col items-center gap-0.5 cursor-pointer group z-20"
      style={{ left: `${pos.x}%`, top: `${pos.y}%`, transform: 'translate(-50%, -50%)' }}
      onClick={onClick}
    >
      <div className={cn(
        'relative rounded-lg p-1 flex items-center justify-center transition-all',
        bg,
        isSelected ? 'scale-115 shadow-lg' : 'hover:scale-105',
        pulse && 'animate-pulse',
      )}>
        <PixelSprite role={role} size={28} />
        {confidence !== undefined && (
          <div className={cn(
            'absolute -bottom-1.5 left-1/2 -translate-x-1/2 px-1 rounded text-[7px] font-mono font-semibold',
            confidence >= 0.8 ? 'bg-success/20 text-success' :
            confidence >= 0.6 ? 'bg-warning/20 text-warning' : 'bg-danger/20 text-danger'
          )}>
            {Math.round(confidence * 100)}%
          </div>
        )}
      </div>
      <span className={cn('text-[8px] font-mono whitespace-nowrap transition-colors', agentTextColor[role], 'group-hover:brightness-125')}>
        {label}
      </span>

      {/* Decision tooltip on hover */}
      {lastMsg && (
        <div className="absolute top-full mt-3 w-56 p-2.5 rounded border border-border bg-popover text-[10px] font-mono opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-xl">
          <div className="flex items-center gap-1 mb-1">
            <StatusBadge status={lastMsg.messageType} className="text-[8px] px-1 py-0" />
            <span className="text-muted-foreground">{new Date(lastMsg.timestamp).toLocaleTimeString()}</span>
          </div>
          <p className="text-foreground leading-relaxed line-clamp-4">{lastMsg.content}</p>
        </div>
      )}
    </div>
  );
}

// ─── Edge SVG with confidence-based animated data flow ─────

function getEdgeConfidence(session: Session, from: AgentRole): number {
  const msg = getLastMessage(session, from);
  return msg?.confidence ?? 0.5;
}

function DialogueEdges({ session, selectedAgent }: { session: Session; selectedAgent: AgentRole | null }) {
  const edges = getActiveEdges(session);

  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none z-10" viewBox="0 0 100 100" preserveAspectRatio="none">
      <defs>
        <marker id="arrowhead" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
          <polygon points="0 0, 6 2, 0 4" fill="hsl(var(--muted-foreground))" opacity="0.5" />
        </marker>
        <marker id="arrowhead-hl" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
          <polygon points="0 0, 6 2, 0 4" fill="hsl(var(--primary))" opacity="0.8" />
        </marker>
        {/* Glow filters per confidence tier */}
        <filter id="glow-high" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="0.6" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-mid" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="0.4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-low" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="0.3" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {edges.map(([from, to], idx) => {
        const p1 = getAgentPos(from);
        const p2 = getAgentPos(to);
        const isHighlighted = selectedAgent === from || selectedAgent === to;
        const pathId = `edge-${from}-${to}`;
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const horizontal = Math.abs(dx) >= Math.abs(dy);
        const laneOffset = ((idx % 5) - 2) * 1.2;
        const c1x = horizontal ? p1.x + dx * 0.42 : p1.x + laneOffset;
        const c1y = horizontal ? p1.y + laneOffset : p1.y + dy * 0.42;
        const c2x = horizontal ? p1.x + dx * 0.58 : p2.x + laneOffset;
        const c2y = horizontal ? p2.y + laneOffset : p1.y + dy * 0.58;
        const d = `M ${p1.x} ${p1.y} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;

        // Confidence-based speed & color
        const conf = getEdgeConfidence(session, from);
        const dur = conf >= 0.8 ? 1.2 : conf >= 0.6 ? 2.0 : 3.0;
        const dotColor = conf >= 0.8 ? 'hsl(var(--success))' : conf >= 0.6 ? 'hsl(var(--warning))' : 'hsl(var(--danger))';
        const glowFilter = conf >= 0.8 ? 'url(#glow-high)' : conf >= 0.6 ? 'url(#glow-mid)' : 'url(#glow-low)';
        const dotR = isHighlighted ? 0.9 : 0.6;
        const trailR = isHighlighted ? 0.5 : 0.35;

        return (
          <g key={pathId}>
            {/* Edge path */}
            <path
              id={pathId}
              d={d}
              fill="none"
              stroke={isHighlighted ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))'}
              strokeWidth={isHighlighted ? '0.4' : '0.2'}
              strokeDasharray={isHighlighted ? 'none' : '1.5 1'}
              opacity={isHighlighted ? 0.8 : 0.25}
              markerEnd={isHighlighted ? 'url(#arrowhead-hl)' : 'url(#arrowhead)'}
              className="transition-all duration-300"
            />

            {/* Trail dot 1 (behind main dot) */}
            <circle r={trailR} fill={dotColor} opacity={0.2} filter={glowFilter}>
              <animateMotion dur={`${dur}s`} repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" begin={`${dur * 0.08}s`}>
                <mpath href={`#${pathId}`} />
              </animateMotion>
            </circle>
            {/* Trail dot 2 */}
            <circle r={trailR * 0.7} fill={dotColor} opacity={0.12} filter={glowFilter}>
              <animateMotion dur={`${dur}s`} repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" begin={`${dur * 0.15}s`}>
                <mpath href={`#${pathId}`} />
              </animateMotion>
            </circle>

            {/* Main dot with glow */}
            <circle r={dotR} fill={dotColor} opacity={0.9} filter={glowFilter}>
              <animateMotion dur={`${dur}s`} repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1">
                <mpath href={`#${pathId}`} />
              </animateMotion>
            </circle>

            {/* Second flow dot on highlighted edges */}
            {isHighlighted && (
              <>
                <circle r={trailR} fill={dotColor} opacity={0.2} filter={glowFilter}>
                  <animateMotion dur={`${dur}s`} repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" begin={`${dur * 0.58}s`}>
                    <mpath href={`#${pathId}`} />
                  </animateMotion>
                </circle>
                <circle r={dotR * 0.85} fill={dotColor} opacity={0.7} filter={glowFilter}>
                  <animateMotion dur={`${dur}s`} repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" begin={`${dur * 0.5}s`}>
                    <mpath href={`#${pathId}`} />
                  </animateMotion>
                </circle>
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ─── Agent Decision Card (right panel) ─────────────────────

function AgentDecisionCard({ msg, isLatest }: { msg: AgentMessage; isLatest: boolean }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className={cn(
        'rounded border p-2.5 text-xs font-mono cursor-pointer transition-all hover:brightness-110',
        agentColorMap[msg.agentRole] || 'bg-card border-border',
        isLatest && 'ring-1 ring-primary/30',
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <span className={cn('font-semibold', agentTextColor[msg.agentRole])}>{msg.agentName}</span>
          <StatusBadge status={msg.messageType} className="text-[8px] px-1 py-0" />
        </div>
        <div className="flex items-center gap-1.5">
          {msg.confidence !== undefined && <ConfidenceBar value={msg.confidence} className="w-14" />}
          <span className="text-muted-foreground text-[9px]">{new Date(msg.timestamp).toLocaleTimeString()}</span>
        </div>
      </div>
      <p className={cn('text-foreground leading-relaxed', !expanded && 'line-clamp-2')}>{msg.content}</p>
      {expanded && msg.reasoning && (
        <div className="mt-2 p-2 rounded bg-secondary/50 border border-border/50">
          <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Reasoning</p>
          <p className="text-muted-foreground">{msg.reasoning}</p>
        </div>
      )}
    </div>
  );
}

// ─── Conclusion Panel ──────────────────────────────────────

function ConclusionPanel({ session }: { session: Session }) {
  const verdict = session.debate?.pmVerdict;
  const reviewerMsg = getLastMessage(session, 'reviewer');
  const executorMsg = getLastMessage(session, 'executor');

  return (
    <Panel title="Final Decision" actions={<StatusBadge status={session.status} />}>
      <div className="space-y-3">
        {/* PM Verdict */}
        {verdict && (
          <div className="rounded border border-agent-pm/30 bg-agent-pm/5 p-3 text-xs font-mono">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Scale className="h-3.5 w-3.5 text-agent-pm" />
              <span className="text-agent-pm font-semibold">PM Verdict</span>
              {verdict.confidence && <ConfidenceBar value={verdict.confidence} className="w-20 ml-auto" />}
            </div>
            <p className="text-foreground leading-relaxed">{verdict.content}</p>
          </div>
        )}

        {/* Reviewer */}
        {reviewerMsg && (
          <div className={cn(
            'rounded border p-3 text-xs font-mono',
            reviewerMsg.messageType === 'error'
              ? 'border-danger/30 bg-danger/5'
              : 'border-agent-reviewer/30 bg-agent-reviewer/5'
          )}>
            <div className="flex items-center gap-1.5 mb-1.5">
              {reviewerMsg.messageType === 'error'
                ? <XCircle className="h-3.5 w-3.5 text-danger" />
                : <CheckCircle2 className="h-3.5 w-3.5 text-agent-reviewer" />
              }
              <span className={reviewerMsg.messageType === 'error' ? 'text-danger font-semibold' : 'text-agent-reviewer font-semibold'}>
                Risk Review
              </span>
              <StatusBadge status={reviewerMsg.messageType} className="text-[8px] px-1 py-0 ml-auto" />
            </div>
            <p className="text-foreground leading-relaxed">{reviewerMsg.content}</p>
          </div>
        )}

        {/* Trade Result */}
        {session.trade && (
          <div className="rounded border border-border bg-secondary/20 p-3 text-xs font-mono">
            <div className="flex items-center gap-1.5 mb-2">
              <ArrowRight className="h-3.5 w-3.5 text-foreground" />
              <span className="text-foreground font-semibold">Execution</span>
              <StatusBadge status={session.trade.status} className="text-[8px] px-1 py-0 ml-auto" />
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <div className="flex justify-between"><span className="text-muted-foreground">Action</span><span className="text-foreground">{session.trade.action}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Type</span><span className="text-foreground">{session.trade.orderType}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Qty</span><span className="text-foreground">{session.trade.quantity}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Slippage</span><span className="text-foreground">{session.trade.slippageBps}bps</span></div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">PnL</span>
                <span className={session.trade.pnl && session.trade.pnl > 0 ? 'text-success' : 'text-danger'}>
                  ${session.trade.pnl?.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        )}

        {!verdict && !reviewerMsg && !session.trade && (
          <p className="text-xs font-mono text-muted-foreground text-center py-4">Awaiting decision...</p>
        )}
      </div>
    </Panel>
  );
}

// ─── Debate Panel ──────────────────────────────────────────

function DebatePanel({ session }: { session: Session }) {
  if (!session.debate) return null;
  const { bullArgument, bearArgument } = session.debate;

  return (
    <Panel title="Bull vs Bear Debate" actions={
      <Swords className="h-3.5 w-3.5 text-muted-foreground" />
    }>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div className="rounded border border-agent-bull/30 bg-agent-bull/5 p-2.5 text-xs font-mono">
          <div className="flex items-center gap-1 mb-1">
            <span className="text-agent-bull font-semibold">🐂 Bull</span>
            {bullArgument.confidence && <ConfidenceBar value={bullArgument.confidence} className="w-14 ml-auto" />}
          </div>
          <p className="text-foreground leading-relaxed text-[11px]">{bullArgument.content}</p>
        </div>
        <div className="rounded border border-agent-bear/30 bg-agent-bear/5 p-2.5 text-xs font-mono">
          <div className="flex items-center gap-1 mb-1">
            <span className="text-agent-bear font-semibold">🐻 Bear</span>
            {bearArgument.confidence && <ConfidenceBar value={bearArgument.confidence} className="w-14 ml-auto" />}
          </div>
          <p className="text-foreground leading-relaxed text-[11px]">{bearArgument.content}</p>
        </div>
      </div>
    </Panel>
  );
}

// ─── Main Page ─────────────────────────────────────────────

export default function SwarmPage() {
  const [selectedAgent, setSelectedAgent] = useState<AgentRole | null>(null);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [runnerStatus, setRunnerStatus] = useState<{ is_running: boolean; symbol?: string; session_id?: string; error?: string }>({ is_running: false });
  const [runnerBusy, setRunnerBusy] = useState(false);

  const refreshRunnerStatus = async () => {
    try {
      const status = await fetchWorkflowRunnerStatus();
      setRunnerStatus(status);
    } catch (err: any) {
      setRunnerStatus({ is_running: false, error: err?.message || 'status_unavailable' });
    }
  };

  useEffect(() => {
    async function loadLatest() {
      try {
        const history = await fetchSessions();
        if (history.length > 0) {
          const sess = history[0]; // get the latest
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

          let debate = null;
          const bull = messages.find((m: any) => m.agentRole === 'bull_strategist');
          const bear = messages.find((m: any) => m.agentRole === 'bear_strategist');
          const pm = messages.find((m: any) => m.agentRole === 'portfolio_manager');
          
          if (bull && bear && pm) {
            debate = { bullArgument: bull, bearArgument: bear, pmVerdict: pm };
          }

          setCurrentSession({
            id: sess.id,
            symbol: sess.symbol,
            status: sess.status,
            startTime: sess.start_time,
            endTime: sess.end_time || sess.start_time,
            trade: detail.trade_plan ? {
              action: detail.trade_plan.action,
              orderType: 'MARKET',
              triggerCondition: 'N/A',
              quantity: detail.trade_plan.quantity || 0,
              entryPrice: detail.trade_plan.entry_price || 0,
              executedPrice: 0,
              slippageBps: 0,
              fee: 0,
              pnl: 0,
              status: 'FILLED',
              rejectCode: null,
              newBalance: 0,
              timestamp: sess.end_time || sess.start_time,
            } : null,
            orchestrationConfig: mockSessions[0].orchestrationConfig,
            revisionRounds: [],
            messages,
            debate,
            riskGates: [], // TODO: extract from reviewer logs if possible
            reflection: null,
          });
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadLatest();
  }, []);

  useEffect(() => {
    refreshRunnerStatus();
    const timer = window.setInterval(() => {
      refreshRunnerStatus();
    }, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const handleRun = async () => {
    const symbol = currentSession?.symbol || 'BTC/USDT';
    setRunnerBusy(true);
    try {
      await runWorkflow(symbol);
      await refreshRunnerStatus();
    } catch (err) {
      console.error(err);
    } finally {
      setRunnerBusy(false);
    }
  };

  const handleStop = async () => {
    setRunnerBusy(true);
    try {
      await stopWorkflow();
      await refreshRunnerStatus();
    } catch (err) {
      console.error(err);
    } finally {
      setRunnerBusy(false);
    }
  };

  const displayMessages = useMemo(() => {
    if (!currentSession) return [];
    if (!selectedAgent) return currentSession.messages;
    // Show messages involving selected agent + messages to/from it
    const relatedRoles = new Set<AgentRole>([selectedAgent]);
    PIPELINE_EDGES.forEach(([from, to]) => {
      if (from === selectedAgent) relatedRoles.add(to);
      if (to === selectedAgent) relatedRoles.add(from);
    });
    return currentSession.messages.filter(m => relatedRoles.has(m.agentRole));
  }, [currentSession, selectedAgent]);

  if (loading) {
    return <div className="p-8 text-center text-muted-foreground"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2"/> Loading swarm state...</div>;
  }
  if (!currentSession) {
    return <div className="p-8 text-center text-muted-foreground">No sessions available</div>;
  }

  return (
    <div className="space-y-4 animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-mono font-bold text-foreground">Agent Swarm</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">
            Real-time multi-agent decision roundtable · {currentSession.symbol} · {currentSession.messages.length} messages
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn(
            'flex items-center gap-1.5 px-2.5 py-1 rounded border',
            runnerStatus.is_running ? 'border-primary/30 bg-primary/5' : 'border-border bg-secondary/30'
          )}>
            <div className={cn(
              'h-2 w-2 rounded-full',
              runnerStatus.is_running ? 'bg-primary animate-pulse' : 'bg-muted-foreground/60'
            )} />
            <span className={cn(
              'text-xs font-mono',
              runnerStatus.is_running ? 'text-primary' : 'text-muted-foreground'
            )}>
              {runnerStatus.is_running ? 'RUNNING' : 'IDLE'}
            </span>
            {runnerStatus.symbol && (
              <span className="text-[10px] font-mono text-muted-foreground">· {runnerStatus.symbol}</span>
            )}
          </div>
          <button
            onClick={refreshRunnerStatus}
            disabled={runnerBusy}
            className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw className="h-3 w-3" />
            Refresh
          </button>
          <button
            onClick={handleRun}
            disabled={runnerBusy || runnerStatus.is_running}
            className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded border border-success/40 text-success disabled:opacity-50"
          >
            <Play className="h-3 w-3" />
            Run
          </button>
          <button
            onClick={handleStop}
            disabled={runnerBusy || !runnerStatus.is_running}
            className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded border border-danger/40 text-danger disabled:opacity-50"
          >
            <Square className="h-3 w-3" />
            Stop
          </button>
          <StatusBadge status={currentSession.status} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Roundtable (left 2/3) */}
        <div className="lg:col-span-2 space-y-4">
          <Panel title="Agent Roundtable" actions={
            <button
              onClick={() => setSelectedAgent(null)}
              className={cn('text-[10px] font-mono px-2 py-0.5 rounded border transition-colors',
                !selectedAgent ? 'border-primary text-primary' : 'border-border text-muted-foreground hover:text-foreground'
              )}
            >
              Show All
            </button>
          }>
            <div className="relative w-full" style={{ paddingBottom: '78%' }}>
              {TEAM_ZONES.map((zone) => (
                <div
                  key={zone.team}
                  className="absolute rounded-xl border border-border/40 bg-secondary/10"
                  style={{
                    left: `${zone.x}%`,
                    top: `${zone.y}%`,
                    width: `${zone.w}%`,
                    height: `${zone.h}%`,
                    transform: 'translate(-50%, -50%)',
                  }}
                >
                  <span className="absolute -top-3 left-2 text-[10px] font-mono text-muted-foreground bg-background/80 px-1 rounded">
                    {zone.team}
                  </span>
                </div>
              ))}

              <DialogueEdges session={currentSession} selectedAgent={selectedAgent} />

              {AGENT_SEATS.map((seat) => (
                <AgentNode
                  key={seat.role}
                  {...seat}
                  session={currentSession}
                  isSelected={selectedAgent === seat.role}
                  onClick={() => setSelectedAgent(selectedAgent === seat.role ? null : seat.role)}
                />
              ))}
            </div>
          </Panel>

          {/* Debate + Conclusion side by side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <DebatePanel session={currentSession} />
            <ConclusionPanel session={currentSession} />
          </div>
        </div>

        {/* Right panel: Real-time agent decisions */}
        <div className="space-y-4">
          <Panel
            title={selectedAgent
              ? `${AGENT_SEATS.find(s => s.role === selectedAgent)?.label} Dialogue`
              : 'Agent Dialogue Feed'
            }
            actions={
              <div className="flex items-center gap-1.5">
                <MessageSquare className="h-3 w-3 text-muted-foreground" />
                <span className="text-[10px] font-mono text-muted-foreground">{displayMessages.length}</span>
              </div>
            }
          >
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {displayMessages.map((msg, i) => (
                <AgentDecisionCard
                  key={msg.id}
                  msg={msg}
                  isLatest={i === displayMessages.length - 1}
                />
              ))}
              {displayMessages.length === 0 && (
                <p className="text-xs font-mono text-muted-foreground text-center py-8">No messages</p>
              )}
            </div>
          </Panel>

          {/* Risk Gates */}
          <Panel title="Risk Gates">
            <div className="space-y-1.5">
              {currentSession.riskGates.map((gate, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
                  <div>
                    <span className="text-xs font-mono text-foreground">{gate.name}</span>
                    <p className="text-[9px] font-mono text-muted-foreground">{gate.detail}</p>
                  </div>
                  <StatusBadge status={gate.status} className="text-[8px] px-1 py-0" />
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
