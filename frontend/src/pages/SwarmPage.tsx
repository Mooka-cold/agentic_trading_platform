import { mockSessions, mockAgents } from '@/data/mock';
import { StatusBadge, Panel, ConfidenceBar, agentColorMap } from '@/components/shared/StatusBadge';
import { cn } from '@/lib/utils';
import { formatTimeCN } from '@/lib/time';
import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { AgentMessage, Session, AgentRole, DebateTurn, FinalizeLog } from '@/types';
import { Scale, Swords, ChevronDown, ChevronUp, MessageSquare, ArrowRight, CheckCircle2, XCircle, AlertTriangle, Loader2, Play, Square, RefreshCw } from 'lucide-react';
import { fetchSessions, fetchSessionDetail, fetchWorkflowRunnerStatus, runWorkflow, stopWorkflow } from '@/data/api';

// ─── Agent seat definitions ────────────────────────────────

const AGENT_SEATS: { role: AgentRole; label: string; shortLabel: string; x: number; y: number; team: string; isMarket?: boolean; isDecision?: boolean; isArbitrator?: boolean; isRisk?: boolean; isExecutor?: boolean }[] = [
  { role: 'market', label: 'Market Scanner', shortLabel: 'MKT', x: 16, y: 16, team: 'Data Team', isMarket: true },
  { role: 'macro', label: 'Macro Analyst', shortLabel: 'MAC', x: 34, y: 16, team: 'Data Team', isMarket: true },
  { role: 'sentiment', label: 'Sentiment Gauge', shortLabel: 'SNT', x: 16, y: 34, team: 'Data Team', isMarket: true },
  { role: 'onchain', label: 'Onchain Monitor', shortLabel: 'OCH', x: 34, y: 34, team: 'Data Team', isMarket: true },
  { role: 'analyst', label: 'Chief Analyst', shortLabel: 'ANA', x: 66, y: 18, team: 'Strategy Team', isDecision: true },
  { role: 'bull_strategist', label: 'Bull Strategist', shortLabel: 'BULL', x: 58, y: 34, team: 'Strategy Team', isDecision: true },
  { role: 'bear_strategist', label: 'Bear Strategist', shortLabel: 'BEAR', x: 78, y: 34, team: 'Strategy Team', isDecision: true },
  { role: 'portfolio_manager', label: 'Portfolio Manager', shortLabel: 'PM', x: 18, y: 66, team: 'Risk Team', isArbitrator: true },
  { role: 'reviewer', label: 'Risk Reviewer', shortLabel: 'REV', x: 34, y: 82, team: 'Risk Team', isRisk: true },
  { role: 'executor', label: 'Trade Executor', shortLabel: 'EXE', x: 66, y: 66, team: 'Execution Team', isExecutor: true },
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

// ─── Dynamic Agent Node Generation from Team Config ──────────

function generateAgentSeats(teamConfig: any) {
  if (!teamConfig) return AGENT_SEATS; // Fallback to default
  
  const dynamicSeats: any[] = [];
  
  // Market Analysts
  const marketAgents = (teamConfig.market_agent_ids || []).filter(Boolean);
  marketAgents.forEach((id: string, idx: number) => {
    const xOffset = 15 + (idx % 2) * 20;
    const yOffset = 15 + Math.floor(idx / 2) * 15;
    dynamicSeats.push({ role: id, label: id, shortLabel: id.substring(0, 3).toUpperCase(), x: xOffset, y: yOffset, team: 'Data Team', isMarket: true });
  });

  // Strategy Masters
  const strategyAgents = (teamConfig.strategy_agent_ids || []).filter(Boolean);
  strategyAgents.forEach((id: string, idx: number) => {
    const xOffset = 60 + (idx % 2) * 20;
    const yOffset = 15 + Math.floor(idx / 2) * 15;
    dynamicSeats.push({ role: id, label: id, shortLabel: id.substring(0, 3).toUpperCase(), x: xOffset, y: yOffset, team: 'Strategy Team', isStrategy: true });
  });

  // Finalizer
  if (teamConfig.finalizer_agent_id) {
    dynamicSeats.push({ role: teamConfig.finalizer_agent_id, label: teamConfig.finalizer_agent_id, shortLabel: 'FIN', x: 25, y: 66, team: 'Risk Team', isFinalizer: true });
  }

  // Risk (multi-sig)
  const riskAgents = (teamConfig.risk_agent_ids || []).filter(Boolean);
  riskAgents.forEach((id: string, idx: number) => {
    dynamicSeats.push({ role: id, label: id, shortLabel: 'RSK', x: 25, y: 82 + idx * 9, team: 'Risk Team', isRisk: true });
  });

  return dynamicSeats.length > 0 ? dynamicSeats : AGENT_SEATS;
}

function generatePipelineEdges(seats: any[]): [string, string][] {
  const edges: [string, string][] = [];

  const marketAgents = seats.filter(s => s.isMarket).map(s => s.role);
  const strategyAgents = seats.filter(s => s.isStrategy).map(s => s.role);
  const finalizer = seats.find(s => s.isFinalizer)?.role;
  const riskAgents = seats.filter(s => s.isRisk).map(s => s.role);

  // Market -> Strategy
  marketAgents.forEach(m => {
    strategyAgents.forEach(d => {
      edges.push([m, d]);
    });
  });

  // Strategy -> Finalizer
  if (finalizer) {
    strategyAgents.forEach(d => {
      edges.push([d, finalizer]);
    });
  }

  // Finalizer -> Risk (multi-sig)
  if (finalizer) {
    riskAgents.forEach(r => {
      edges.push([finalizer, r]);
    });
  }

  return edges.length > 0 ? edges : PIPELINE_EDGES as any;
}

// ─── Helpers ───────────────────────────────────────────────

function getAgentPos(role: string, seats: any[]) {
  const seat = seats.find(s => s.role === role);
  return seat ? { x: seat.x, y: seat.y } : { x: 50, y: 50 };
}

function getLastMessage(session: Session, role: AgentRole): AgentMessage | undefined {
  const msgs = session.messages.filter(m => m.agentRole === role);
  return msgs.length > 0 ? msgs[msgs.length - 1] : undefined;
}

function getActiveEdges(session: Session, dynamicEdges: [string, string][]): [string, string][] {
  const activeRoles = new Set(session.messages.map(m => m.agentRole));
  return dynamicEdges.filter(([from, to]) => activeRoles.has(from) && activeRoles.has(to));
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

function AgentNode({ role, label, shortLabel, session, isSelected, onClick, dynamicSeats }: {
  role: string; label: string; shortLabel: string;
  session: Session; isSelected: boolean; onClick: () => void; dynamicSeats: any[];
}) {
  const pos = getAgentPos(role, dynamicSeats);
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
            <span className="text-muted-foreground">{formatTimeCN(lastMsg.timestamp)}</span>
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

function DialogueEdges({ session, selectedAgent, dynamicEdges, dynamicSeats }: { session: Session; selectedAgent: string | null; dynamicEdges: [string, string][]; dynamicSeats: any[] }) {
  const edges = getActiveEdges(session, dynamicEdges);

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
        const p1 = getAgentPos(from, dynamicSeats);
        const p2 = getAgentPos(to, dynamicSeats);
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

function AgentDecisionCard({ msg, isLatest, alignRight, seatLabel }: { msg: AgentMessage; isLatest: boolean; alignRight: boolean; seatLabel?: string }) {
  const [expanded, setExpanded] = useState(false);
  const bgColor = agentColorMap[msg.agentRole] || 'bg-card border-border';
  const textColor = agentTextColor[msg.agentRole] || 'text-foreground';

  return (
    <div className={cn('flex w-full mb-3', alignRight ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'relative max-w-[85%] rounded-lg border p-2.5 text-xs font-mono cursor-pointer transition-all hover:brightness-110 shadow-sm',
          bgColor,
          isLatest && 'ring-1 ring-primary/30',
          alignRight ? 'rounded-tr-none' : 'rounded-tl-none'
        )}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Chat Bubble Tail */}
        <div 
          className={cn(
            'absolute top-0 w-3 h-3 border-t border-border',
            alignRight 
              ? '-right-1.5 border-r bg-inherit rotate-45 translate-x-1/2 translate-y-1' 
              : '-left-1.5 border-l bg-inherit -rotate-45 -translate-x-1/2 translate-y-1'
          )}
          style={{ backgroundColor: 'inherit', borderBottomColor: 'transparent', borderRightColor: alignRight ? 'inherit' : 'transparent', borderLeftColor: !alignRight ? 'inherit' : 'transparent' }}
        />

        <div className={cn('flex items-center gap-1.5 mb-1.5', alignRight ? 'flex-row-reverse' : '')}>
          <div className="flex items-center gap-1">
            <span className={cn('font-bold', textColor)}>{seatLabel || msg.agentName}</span>
            <StatusBadge status={msg.messageType} className="text-[8px] px-1 py-0 scale-90 origin-left" />
          </div>
          <div className="flex items-center gap-1 opacity-70 ml-auto mr-auto">
            {msg.confidence !== undefined && <ConfidenceBar value={msg.confidence} className="w-12" />}
          </div>
          <span className="text-muted-foreground text-[8px]">{formatTimeCN(msg.timestamp)}</span>
        </div>
        
        <p className={cn('text-foreground leading-relaxed', !expanded && 'line-clamp-3')}>{msg.content}</p>
        
        {expanded && msg.reasoning && (
          <div className="mt-2 p-2 rounded bg-background/50 border border-border/50">
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Reasoning</p>
            <p className="text-muted-foreground">{msg.reasoning}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Conclusion Panel ──────────────────────────────────────

function ConclusionPanel({ session, dynamicSeats }: { session: Session; dynamicSeats: any[] }) {
  const arbitratorRole = dynamicSeats.find(s => s.isArbitrator)?.role;
  const riskRole = dynamicSeats.find(s => s.isRisk)?.role;
  
  const verdictMsg = arbitratorRole ? getLastMessage(session, arbitratorRole) : undefined;
  const reviewerMsg = riskRole ? getLastMessage(session, riskRole) : undefined;

  const arbitratorSeat = dynamicSeats.find(s => s.role === arbitratorRole);
  const riskSeat = dynamicSeats.find(s => s.role === riskRole);

  return (
    <Panel title="Final Decision" actions={<StatusBadge status={session.status} />}>
      <div className="space-y-3">
        {/* PM Verdict */}
        {verdictMsg && (
          <div className="rounded border border-agent-pm/30 bg-agent-pm/5 p-3 text-xs font-mono">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Scale className="h-3.5 w-3.5 text-agent-pm" />
              <span className="text-agent-pm font-semibold">{arbitratorSeat ? arbitratorSeat.label : 'Arbitrator'} Verdict</span>
              {verdictMsg.confidence && <ConfidenceBar value={verdictMsg.confidence} className="w-20 ml-auto" />}
            </div>
            <p className="text-foreground leading-relaxed">{verdictMsg.content}</p>
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
                {riskSeat ? riskSeat.label : 'Risk Review'}
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

        {!verdictMsg && !reviewerMsg && !session.trade && (
          <p className="text-xs font-mono text-muted-foreground text-center py-4">Awaiting decision...</p>
        )}
      </div>
    </Panel>
  );
}

// ─── Debate Panel ──────────────────────────────────────────

function DebatePanel({ session, dynamicSeats }: { session: Session; dynamicSeats: any[] }) {
  // Prefer the structured multi-round debate thread (persisted via log_type='debate').
  // Fall back to the legacy single-round proposal view if no structured turns exist.
  const turns: DebateTurn[] = (session.debateTurns || []) as DebateTurn[];

  if (turns.length > 0) {
    return <MultiRoundDebateView turns={turns} finalizeLog={session.finalizeLog} dynamicSeats={dynamicSeats} />;
  }

  // Legacy single-round fallback
  const decisionRoles = new Set(dynamicSeats.filter(s => s.isDecision).map(s => s.role));
  const proposals = Array.from(decisionRoles).map(role => getLastMessage(session, role)).filter(Boolean) as AgentMessage[];

  if (proposals.length === 0) return null;

  return (
    <Panel title="Strategist Proposals" actions={
      <Swords className="h-3.5 w-3.5 text-muted-foreground" />
    }>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[300px] overflow-y-auto scrollbar-thin pr-1">
        {proposals.map((prop, idx) => {
          const colorClass = agentColorMap[prop.agentRole] || (idx % 2 === 0 ? 'bg-agent-bull/5 border-agent-bull/30' : 'bg-agent-bear/5 border-agent-bear/30');
          const textClass = agentTextColor[prop.agentRole] || (idx % 2 === 0 ? 'text-agent-bull' : 'text-agent-bear');
          const seat = dynamicSeats.find(s => s.role === prop.agentRole);

          return (
            <div key={prop.id} className={cn("rounded border p-2.5 text-xs font-mono", colorClass)}>
              <div className="flex items-center gap-1 mb-1">
                <span className={cn("font-semibold", textClass)}>
                  {seat ? seat.label : prop.agentName}
                </span>
                {prop.confidence !== undefined && <ConfidenceBar value={prop.confidence} className="w-14 ml-auto" />}
              </div>
              <p className="text-foreground leading-relaxed text-[11px] line-clamp-4 hover:line-clamp-none transition-all">{prop.content}</p>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ─── Multi-Round Debate View (chronological thread) ────────

function MultiRoundDebateView({ turns, finalizeLog, dynamicSeats }: { turns: DebateTurn[]; finalizeLog?: FinalizeLog | null; dynamicSeats: any[] }) {
  // Group turns by round so the user can read R1 (independent) → R2 (rebuttals) cleanly.
  const rounds = useMemo(() => {
    const m: Record<number, DebateTurn[]> = {};
    for (const t of turns) {
      const r = t.round || 1;
      (m[r] ||= []).push(t);
    }
    return Object.keys(m).map(Number).sort((a, b) => a - b).map(r => ({ round: r, turns: m[r] }));
  }, [turns]);

  const [expanded, setExpanded] = useState<Record<number, boolean>>({ 1: true, 2: true });

  const seatLabel = (agentId: string) => {
    const seat = dynamicSeats.find(s => s.role === agentId);
    return seat ? seat.label : (agentId || '').toUpperCase();
  };

  return (
    <Panel
      title="Strategy Debate Thread"
      actions={
        <div className="flex items-center gap-2">
          <Swords className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[10px] font-mono text-muted-foreground">{turns.length} turns · {rounds.length} rounds</span>
        </div>
      }
    >
      <div className="space-y-3 max-h-[420px] overflow-y-auto scrollbar-thin pr-1">
        {rounds.map(({ round, turns: roundTurns }) => {
          const isOpen = expanded[round] ?? true;
          const isRebuttalRound = round > 1;
          return (
            <div key={round} className={cn(
              "rounded border p-2.5",
              isRebuttalRound ? "border-agent-bull/30 bg-agent-bull/5" : "border-border bg-card"
            )}>
              <button
                onClick={() => setExpanded(prev => ({ ...prev, [round]: !(prev[round] ?? true) }))}
                className="w-full flex items-center justify-between text-left"
              >
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "text-[10px] font-mono font-bold px-1.5 py-0.5 rounded",
                    isRebuttalRound ? "bg-agent-bull/20 text-agent-bull" : "bg-primary/15 text-primary"
                  )}>
                    R{round}
                  </span>
                  <span className="text-xs font-semibold text-foreground">
                    {isRebuttalRound ? "Rebuttal Round" : "Opening Round (Independent)"}
                  </span>
                  <span className="text-[10px] text-muted-foreground font-mono">{roundTurns.length} speakers</span>
                </div>
                {isOpen ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
              </button>

              {isOpen && (
                <div className="mt-2 space-y-2">
                  {roundTurns.map((turn, idx) => {
                    const isFinalizerPick = finalizeLog?.debate_turn_ids?.includes(`R${turn.round}_${turn.agent_id}`);
                    return (
                      <div key={`${turn.round}-${turn.agent_id}-${idx}`} className={cn(
                        "rounded border p-2 text-[11px] font-mono",
                        isFinalizerPick ? "border-primary/50 bg-primary/5" : "border-border/50 bg-background/40"
                      )}>
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="font-semibold text-foreground">{seatLabel(turn.agent_id)}</span>
                          <span className={cn(
                            "inline-flex items-center rounded text-[9px] font-bold px-1.5 py-0.5",
                            turn.action === 'BUY' || turn.action === 'LONG' ? "bg-success/20 text-success" :
                            turn.action === 'SELL' || turn.action === 'SHORT' || turn.action === 'COVER' ? "bg-danger/20 text-danger" :
                            "bg-muted text-muted-foreground"
                          )}>
                            {turn.action}
                          </span>
                          {typeof turn.confidence === 'number' && <ConfidenceBar value={turn.confidence} className="w-14 ml-auto" />}
                          {isFinalizerPick && <span className="text-[9px] text-primary font-bold">★ finalizer cited</span>}
                        </div>

                        <p className="text-foreground leading-relaxed mb-1">
                          <span className="text-[9px] text-muted-foreground uppercase mr-1">thesis</span>
                          {turn.thesis}
                        </p>

                        {turn.rebuttals && turn.rebuttals.length > 0 && (
                          <div className="mt-1 pl-2 border-l-2 border-agent-bull/40">
                            <span className="text-[9px] text-muted-foreground uppercase">rebuttals</span>
                            <ul className="mt-0.5 space-y-0.5">
                              {turn.rebuttals.map((r, i) => (
                                <li key={i} className="text-foreground/90 text-[11px] leading-snug">
                                  <span className="text-agent-bull">↳</span> {r}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {turn.references && turn.references.length > 0 && (
                          <div className="mt-1 text-[9px] text-muted-foreground">
                            → responded to: {turn.references.map(r => seatLabel(r)).join(', ')}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {/* Finalizer audit trail */}
        {finalizeLog && (
          <div className="rounded border border-primary/40 bg-primary/5 p-2.5">
            <div className="flex items-center gap-2 mb-1">
              <Scale className="h-3.5 w-3.5 text-primary" />
              <span className="text-xs font-semibold text-primary">Finalizer Decision</span>
              <span className="ml-auto text-[10px] font-mono text-primary">{finalizeLog.final_action} @ {(finalizeLog.final_confidence * 100).toFixed(0)}%</span>
            </div>
            <p className="text-[11px] text-foreground leading-relaxed line-clamp-3 hover:line-clamp-none transition-all">{finalizeLog.reasoning}</p>
            <div className="mt-1 text-[9px] text-muted-foreground">
              Cited {finalizeLog.debate_turn_ids?.length || 0} debate turns: {finalizeLog.debate_turn_ids?.join(' · ')}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ─── Main Page ─────────────────────────────────────────────

export default function SwarmPage() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [teamConfig, setTeamConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [runnerStatus, setRunnerStatus] = useState<{ is_running: boolean; symbol?: string; session_id?: string; error?: string }>({ is_running: false });
  const [runnerBusy, setRunnerBusy] = useState(false);

  // Derive dynamic state
  const dynamicSeats = useMemo(() => generateAgentSeats(teamConfig), [teamConfig]);
  const dynamicEdges = useMemo(() => generatePipelineEdges(dynamicSeats), [dynamicSeats]);

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
        try {
          const configRes = await fetch('/api/v1/system/team-config', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
          });
          if (configRes.ok) {
            setTeamConfig(await configRes.json());
          }
        } catch (e) {
          console.warn("Failed to load team config", e);
        }
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

          // ── Reconstruct the structured debate thread from persisted log artifacts ──
          // Each `debate`-type log emitted by GenericDecisionAgent.run_debate_round
          // contains the full DebateTurn JSON (round, agent_id, thesis, rebuttals,
          // references, confidence, action, timestamp). Sorting by round gives us
          // a chronological debate timeline that survives SSE misses.
          const debateTurns: any[] = detail.logs
            .filter((l: any) => l.type === 'debate' && l.artifact)
            .map((l: any) => l.artifact)
            .sort((a: any, b: any) => (a.round || 0) - (b.round || 0) || String(a.agent_id).localeCompare(String(b.agent_id)));

          // Finalizer's "FINALIZE_BY_*" log captures which debate turns the
          // arbitrator actually relied on. We surface it for the conclusion panel.
          const finalizeLog = detail.logs.find((l: any) => l.type === 'finalize');

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
              id: `trade-${sess.id}`,
              sessionId: sess.id,
              symbol: sess.symbol,
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
            debateTurns,        // full chronological DebateTurn list
            finalizeLog: finalizeLog?.artifact || null,  // finalizer audit trail
            riskGates: [],
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
    // 轮询刷新当前 session 数据，以实现实时滚动
    const timer = window.setInterval(() => {
      loadLatest();
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
    const relatedRoles = new Set<string>([selectedAgent]);
    dynamicEdges.forEach(([from, to]) => {
      if (from === selectedAgent) relatedRoles.add(to);
      if (to === selectedAgent) relatedRoles.add(from);
    });
    return currentSession.messages.filter(m => relatedRoles.has(m.agentRole));
  }, [currentSession, selectedAgent, dynamicEdges]);

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

              <DialogueEdges session={currentSession} selectedAgent={selectedAgent} dynamicEdges={dynamicEdges} dynamicSeats={dynamicSeats} />

              {dynamicSeats.map((seat) => (
                <AgentNode
                  key={seat.role}
                  {...seat}
                  session={currentSession}
                  isSelected={selectedAgent === seat.role}
                  onClick={() => setSelectedAgent(selectedAgent === seat.role ? null : seat.role)}
                  dynamicSeats={dynamicSeats}
                />
              ))}
            </div>
          </Panel>

          {/* Debate + Conclusion side by side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <DebatePanel session={currentSession} dynamicSeats={dynamicSeats} />
            <ConclusionPanel session={currentSession} dynamicSeats={dynamicSeats} />
          </div>
        </div>

        {/* Right panel: Real-time agent decisions */}
        <div className="space-y-4">
          <Panel
            title={selectedAgent
              ? `${dynamicSeats.find(s => s.role === selectedAgent)?.label || selectedAgent} Dialogue`
              : 'Agent Dialogue Feed'
            }
            actions={
              <div className="flex items-center gap-1.5">
                <MessageSquare className="h-3 w-3 text-muted-foreground" />
                <span className="text-[10px] font-mono text-muted-foreground">{displayMessages.length}</span>
              </div>
            }
          >
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-3 scrollbar-thin">
              {displayMessages.map((msg, i) => {
                const seat = dynamicSeats.find(s => s.role === msg.agentRole);
                // Ensure alignRight is always a boolean, defaulting to false if undefined
                const alignRight = seat ? !!(seat.isArbitrator || seat.isRisk || seat.isExecutor) : false;
                
                return (
                  <AgentDecisionCard
                    key={msg.id}
                    msg={msg}
                    isLatest={i === displayMessages.length - 1}
                    alignRight={alignRight}
                    seatLabel={seat ? seat.label : undefined}
                  />
                );
              })}
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
