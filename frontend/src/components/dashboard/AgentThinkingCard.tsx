"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Activity, 
  X,
  Cpu,
  ArrowRight,
  MessageSquare,
  AlertCircle,
  Square,
  Play,
  Wallet,
  TrendingUp,
  TrendingDown,
  DollarSign
} from "lucide-react";
import { MarketAPI } from "@/lib/api/market";
import { formatTime } from "@/lib/utils";

// --- Types ---

type AgentStatus = "idle" | "working" | "success" | "error";

interface AgentLog {
  id: string;
  timestamp: string;
  session_id?: string; // Add session_id
  type: "input" | "process" | "output" | "info";
  content: string;
  artifact?: Record<string, any> | null;
}

interface AgentConfig {
  id: string;
  name: string;
  role: string;
  avatarSeed: string; // Seed for DiceBear Pixel Art
  description: string;
  color: string; // Unique color for the agent
}

interface AgentState {
  status: AgentStatus;
  currentInput?: string;
  currentOutput?: string;
  logs: AgentLog[];
  artifact?: Record<string, any>;
}

interface Position {
    symbol: string;
    side: 'LONG' | 'SHORT';
    entry_price: number;
    current_price: number; // Need to fetch or estimate
    quantity: number;
    pnl?: number;
    pnl_percent?: number;
}

// --- Configuration (Based on ai_engine/prompts) ---

const AGENTS: AgentConfig[] = [
  { 
    id: "analyst", 
    name: "The Analyst", 
    role: "Market Scanner", 
    avatarSeed: "Analyst", 
    description: "Scans market data and technical indicators.",
    color: "#3b82f6" // Blue
  },
  { 
    id: "strategist", 
    name: "The Strategist", 
    role: "Strategy Generator", 
    avatarSeed: "Strategist", 
    description: "Formulates trading plans based on analysis.",
    color: "#8b5cf6" // Violet
  },
  { 
    id: "reviewer", 
    name: "The Reviewer", 
    role: "Risk Manager", 
    avatarSeed: "Reviewer", 
    description: "Validates strategies against risk rules.",
    color: "#ef4444" // Red
  },
  { 
    id: "reflector", 
    name: "The Reflector", 
    role: "Feedback Loop", 
    avatarSeed: "Reflector", 
    description: "Reviews past performance to improve future decisions.",
    color: "#10b981" // Emerald
  }
];

// --- Components ---

const PixelAvatar = ({ seed, size = 40, isWorking }: { seed: string, size?: number, isWorking?: boolean }) => {
  return (
    <div style={{ 
      width: size, 
      height: size, 
      overflow: 'hidden', 
      borderRadius: '8px', 
      backgroundColor: '#1e293b', 
      border: isWorking ? '2px solid white' : '2px solid #334155',
      position: 'relative',
      transition: 'all 0.3s'
    }}>
        {/* Pixel Art Image */}
        <img 
            src={`https://api.dicebear.com/9.x/pixel-art/svg?seed=${seed}&backgroundColor=transparent`} 
            alt={seed} 
            style={{ width: '100%', height: '100%', objectFit: 'cover', imageRendering: 'pixelated' }} 
        />
        
        {/* Working Animation Overlay */}
        {isWorking && (
             <motion.div 
                animate={{ opacity: [0, 0.5, 0] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
                style={{ 
                    position: 'absolute', 
                    top: 0, 
                    left: 0, 
                    right: 0, 
                    bottom: 0, 
                    backgroundColor: 'white',
                    mixBlendMode: 'overlay' 
                }}
             />
        )}
    </div>
  );
};

const AgentNode = ({ 
  config, 
  state, 
  onClick 
}: { 
  config: AgentConfig; 
  state: AgentState; 
  onClick: () => void;
}) => {
  const isWorking = state.status === "working";
  const isIdle = state.status === "idle";
  const isSuccess = state.status === "success";

  // Dynamic Styles based on state
  const bgStyle = isWorking 
    ? `linear-gradient(135deg, ${config.color}20 0%, #0f172a 100%)` // Tinted background
    : '#0f172a';

  const borderStyle = isWorking
    ? `1px solid ${config.color}`
    : '1px solid #1e293b';

  const parseCardDecision = (content?: string) => {
    if (!content) return {};
    const body = content.startsWith("DECISION:") ? content.slice(9).trim() : content.startsWith("PROPOSAL:") ? content.slice(9).trim() : content;
    const parts = body.replace(/\n/g, "|").split("|").map((x) => x.trim()).filter(Boolean);
    const meta: Record<string, string> = {};
    const first = parts[0] || "";
    if (first && !first.includes(":")) meta.action = first;
    parts.forEach((p) => {
      const idx = p.indexOf(":");
      if (idx > 0) {
        const k = p.slice(0, idx).trim().toLowerCase().replace(/\//g, "_");
        const v = p.slice(idx + 1).trim();
        meta[k] = v;
      }
    });
    return meta;
  };

  const parseCardReasoning = (reasoning?: string) => {
    if (!reasoning) return [];
    return reasoning
      .split("||")
      .map((x) => x.trim())
      .filter(Boolean)
      .map((part) => {
        const idx = part.indexOf(":");
        if (idx <= 0) return { label: "理由", value: part };
        const key = part.slice(0, idx).trim().toUpperCase();
        const labelMap: Record<string, string> = {
          TRIGGER: "触发条件",
          INVALIDATION: "失效条件",
          FAILSAFE: "保护动作"
        };
        return {
          label: labelMap[key] || key,
          value: part.slice(idx + 1).trim()
        };
      });
  };

  return (
    <motion.div
      onClick={onClick}
      whileHover={{ scale: 1.02, translateY: -2 }}
      whileTap={{ scale: 0.98 }}
      style={{
        background: bgStyle,
        border: borderStyle,
        borderRadius: '16px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        cursor: 'pointer',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: isWorking ? `0 0 20px ${config.color}40` : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        transition: 'all 0.3s',
        height: '100%' // Ensure full height in grid
      }}
    >
      {/* Header: Avatar + Info */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
        <PixelAvatar seed={config.avatarSeed} size={48} isWorking={isWorking} />
        
        <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '800', color: isWorking ? 'white' : '#e2e8f0', fontFamily: '"Press Start 2P", system-ui, sans-serif' }}>
                    {config.name}
                </h3>
                {/* Status Dot */}
                <div style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: isWorking ? config.color : isSuccess ? '#22c55e' : '#475569',
                    boxShadow: isWorking ? `0 0 8px ${config.color}` : 'none'
                }} />
            </div>
            <span style={{ fontSize: '11px', color: config.color, fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                {config.role}
            </span>
        </div>
      </div>

      {/* Speech Bubble (Input/Output) */}
      <div style={{ marginTop: '16px', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
        {(state.currentInput || state.currentOutput) ? (
             <div style={{ 
                backgroundColor: '#1e293b', 
                borderRadius: '8px', 
                padding: '10px', 
                borderLeft: `3px solid ${state.currentOutput ? '#22c55e' : config.color}`,
                fontSize: '11px',
                fontFamily: 'monospace',
                position: 'relative'
             }}>
                {/* Tail */}
                <div style={{ 
                    position: 'absolute', 
                    top: '-6px', 
                    left: '20px', 
                    width: '0', 
                    height: '0', 
                    borderLeft: '6px solid transparent', 
                    borderRight: '6px solid transparent', 
                    borderBottom: '6px solid #1e293b' 
                }} />
                
                {state.currentOutput ? (
                    (() => {
                        const parsed = parseCardDecision(state.currentOutput);
                        const action = (state.artifact?.action as string | undefined) || (parsed.action as string | undefined);
                        const actionLabelMap: Record<string, string> = { BUY: "开多", SELL: "平多", SHORT: "开空", COVER: "平空", HOLD: "观望", CLOSE: "平仓" };
                        const confidence = (typeof state.artifact?.confidence === 'number' ? Number(state.artifact.confidence).toFixed(2) : parsed.confidence) || undefined;
                        const rr = (state.artifact?.rr as string | undefined) || (parsed.r_r as string | undefined);
                        const decisionReasoning = typeof state.artifact?.reasoning === 'string' ? state.artifact.reasoning : (parsed.reason || "");
                        const reasoningBlocks = parseCardReasoning(decisionReasoning);
                        const isDecision = state.currentOutput.startsWith("DECISION:") || state.currentOutput.startsWith("PROPOSAL:");
                        const genericBlocks: Array<{label: string, value: string}> = [];
                        const genericChips: string[] = [];
                        const reviewerCheckRows = !isDecision && config.id === "reviewer" ? toReviewerCheckRows(state.artifact) : [];
                        if (!isDecision && state.artifact) {
                          if (config.id === "analyst") {
                            if (state.artifact.bias) genericChips.push(`偏向 ${String(state.artifact.bias)}`);
                            if (state.artifact.risk) genericBlocks.push({ label: "核心风险", value: String(state.artifact.risk) });
                            if (state.artifact.reasoning) genericBlocks.push({ label: "分析逻辑", value: String(state.artifact.reasoning) });
                          } else if (config.id === "sentiment") {
                            if (typeof state.artifact.score === "number") genericChips.push(`情绪分 ${Number(state.artifact.score).toFixed(2)}`);
                            if (Array.isArray(state.artifact.drivers) && state.artifact.drivers.length > 0) {
                              genericBlocks.push({ label: "驱动因素", value: state.artifact.drivers.slice(0, 2).join("；") });
                            }
                          } else if (config.id === "reviewer") {
                            const reviewer = toReviewerSections(state.artifact);
                            genericChips.push(...reviewer.chips);
                            genericBlocks.push(...reviewer.blocks);
                          } else if (config.id === "reflector") {
                            if (state.artifact.status) genericChips.push(`状态 ${String(state.artifact.status)}`);
                            if (state.artifact.insight_preview) genericBlocks.push({ label: "记忆摘要", value: String(state.artifact.insight_preview) });
                          }
                        }
                        if (!isDecision) {
                          return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                              <div style={{ color: '#e2e8f0' }}>
                                <span style={{ color: '#22c55e', fontWeight: 'bold' }}>SAYS:</span> {state.currentOutput}
                              </div>
                              {genericChips.length > 0 && (
                                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                  {genericChips.map((chip, idx) => (
                                    <span key={`chip-${idx}`} style={{ color: '#cbd5e1', fontSize: '10px', border: '1px solid #334155', borderRadius: '999px', padding: '1px 7px' }}>{chip}</span>
                                  ))}
                                </div>
                              )}
                              {genericBlocks.slice(0, 2).map((item, idx) => (
                                <div key={`block-${idx}`} style={{ borderLeft: `2px solid ${config.color}70`, paddingLeft: '6px' }}>
                                  <div style={{ color: config.color, fontSize: '10px', fontWeight: 'bold' }}>{item.label}</div>
                                  <div style={{ color: '#e2e8f0', fontSize: '10px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{item.value}</div>
                                </div>
                              ))}
                              {reviewerCheckRows.length > 0 && (
                                <div style={{ borderLeft: `2px solid ${config.color}70`, paddingLeft: '6px' }}>
                                  <div style={{ color: config.color, fontSize: '10px', fontWeight: 'bold' }}>规则检查</div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '2px' }}>
                                    {reviewerCheckRows.slice(0, 3).map((row, idx) => (
                                      <div key={`review-row-${idx}`} style={{ color: '#cbd5e1', fontSize: '10px' }}>
                                        {row.name}: <span style={{ color: row.status === "PASS" ? '#22c55e' : row.status === "FAIL" ? '#ef4444' : '#eab308' }}>{row.status}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        }
                        return (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                              <span style={{ color: '#22c55e', fontWeight: 'bold', fontSize: '10px' }}>SAYS</span>
                              <span style={{ color: config.color, fontWeight: 'bold', fontSize: '10px' }}>{actionLabelMap[action || ""] || action || "决策"}</span>
                              {confidence && <span style={{ color: '#cbd5e1', fontSize: '10px' }}>置信度 {confidence}</span>}
                              {rr && <span style={{ color: '#cbd5e1', fontSize: '10px' }}>R/R {rr}</span>}
                            </div>
                            {reasoningBlocks.slice(0, 2).map((item, idx) => (
                              <div key={`node-reason-${idx}`} style={{ borderLeft: `2px solid ${config.color}70`, paddingLeft: '6px' }}>
                                <div style={{ color: config.color, fontSize: '10px', fontWeight: 'bold' }}>{item.label}</div>
                                <div style={{ color: '#e2e8f0', fontSize: '10px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{item.value}</div>
                              </div>
                            ))}
                          </div>
                        );
                    })()
                ) : (
                    <div style={{ color: '#94a3b8' }}>
                        <span style={{ color: config.color, fontWeight: 'bold' }}>THINKING:</span> {state.currentInput}...
                    </div>
                )}
             </div>
        ) : (
             <div style={{ 
                backgroundColor: '#1e293b50', 
                borderRadius: '8px', 
                padding: '10px', 
                fontSize: '11px', 
                color: '#475569', 
                textAlign: 'center', 
                fontStyle: 'italic' 
             }}>
                Zzz...
             </div>
        )}
      </div>

      {/* Structured Artifact (New) */}
      {state.artifact && (
          <div style={{ marginTop: '12px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
             {Object.entries(state.artifact).slice(0, 4).map(([k, v]) => (
                 <div key={k} style={{ 
                    backgroundColor: 'rgba(0,0,0,0.3)', 
                    border: `1px solid ${config.color}30`, 
                    borderRadius: '4px', 
                    padding: '4px 8px', 
                    fontSize: '10px', 
                    display: 'flex', 
                    gap: '4px',
                    alignItems: 'center'
                 }}>
                    <span style={{ color: '#94a3b8', textTransform: 'uppercase', fontWeight: 'bold' }}>{k}:</span>
                    <span style={{ color: config.color, fontFamily: 'monospace', fontWeight: 'bold' }}>
                        {typeof v === 'number' ? (v % 1 !== 0 ? v.toFixed(2) : v) : String(v)}
                    </span>
                 </div>
             ))}
          </div>
      )}

      {/* Progress Bar */}
      {isWorking && (
          <motion.div 
            initial={{ width: '0%' }}
            animate={{ width: '100%' }}
            transition={{ duration: 2 }} // Should match mock duration
            style={{ position: 'absolute', bottom: 0, left: 0, height: '4px', backgroundColor: config.color }}
          />
      )}
    </motion.div>
  );
};

const Sparkline = ({ data, color }: { data: number[], color: string }) => {
  if (!data || data.length === 0) return null;
  
  const width = 200;
  const height = 60;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  
  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * height; // Invert Y
    return `${x},${y}`;
  }).join(' ');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '16px' }}>
        <div style={{ fontSize: '10px', color: '#64748b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 'bold', color: color }}>LIVE MARKET FEED (1H)</span>
            <span style={{ fontFamily: 'monospace' }}>{data[data.length-1].toFixed(2)}</span>
        </div>
        <div style={{ 
            border: `1px solid ${color}40`, 
            borderRadius: '8px', 
            padding: '12px', 
            backgroundColor: `${color}08`,
            position: 'relative'
        }}>
            <svg width="100%" height="40" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ overflow: 'visible' }}>
                <polyline
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    points={points}
                    vectorEffect="non-scaling-stroke"
                />
                {/* End Dot */}
                <circle cx={width} cy={height - ((data[data.length-1] - min) / range) * height} r="3" fill={color} />
            </svg>
        </div>
    </div>
  );
};

const parseReasoningBlocks = (reasoning?: string) => {
  if (!reasoning) return [];
  return reasoning
    .split("||")
    .map((x) => x.trim())
    .filter(Boolean)
    .map((part) => {
      const idx = part.indexOf(":");
      if (idx <= 0) return { label: "Reason", value: part };
      return {
        label: part.slice(0, idx).trim().toUpperCase(),
        value: part.slice(idx + 1).trim()
      };
    });
};

const reasoningLabelMap: Record<string, string> = {
  TRIGGER: "触发条件",
  INVALIDATION: "失效条件",
  FAILSAFE: "保护动作",
  REASON: "理由"
};

const actionLabelMap: Record<string, string> = {
  BUY: "开多",
  SELL: "平多",
  SHORT: "开空",
  COVER: "平空",
  HOLD: "观望",
  CLOSE: "平仓"
};

const parseDecisionFromContent = (content?: string) => {
  if (!content) return {};
  const body = content.startsWith("DECISION:") ? content.slice(9).trim() : content.startsWith("PROPOSAL:") ? content.slice(9).trim() : "";
  if (!body) return {};
  const parts = body.replace(/\n/g, "|").split("|").map((x) => x.trim()).filter(Boolean);
  const meta: Record<string, string> = {};
  const first = parts[0] || "";
  if (first && !first.includes(":")) {
    meta.action = first;
  }
  parts.forEach((p) => {
    const idx = p.indexOf(":");
    if (idx > 0) {
      const k = p.slice(0, idx).trim().toLowerCase().replace(/\//g, "_");
      const v = p.slice(idx + 1).trim();
      meta[k] = v;
    }
  });
  return meta;
};

const reviewerCheckLabelMap: Record<string, string> = {
  contract: "契约完整性",
  sl_side: "止损方向",
  tp_side: "止盈方向",
  direction: "方向一致性",
  sl_distance: "止损距离",
  rr_ratio: "风险收益比"
};

const toReviewerSections = (artifact: any) => {
  const chips: string[] = [];
  const blocks: Array<{ label: string; value: string }> = [];
  if (!artifact || typeof artifact !== "object") {
    return { chips, blocks };
  }
  const verdict = artifact.verdict;
  const score = artifact.score;
  const code = artifact.code || artifact.reject_code;
  const reason = artifact.reason;
  const checks = artifact.checks && typeof artifact.checks === "object" ? artifact.checks : null;
  const fixSuggestions = artifact.fix_suggestions && typeof artifact.fix_suggestions === "object" ? artifact.fix_suggestions : null;
  if (verdict) chips.push(`结论 ${String(verdict)}`);
  if (score != null) chips.push(`风险分 ${String(score)}`);
  if (code) chips.push(`代码 ${String(code)}`);
  if (reason) blocks.push({ label: "原因", value: String(reason) });
  if (checks) {
    const rows = Object.entries(checks).map(([k, v]) => `${reviewerCheckLabelMap[k] || k}: ${String(v)}`);
    if (rows.length > 0) blocks.push({ label: "规则检查", value: rows.join("；") });
  }
  if (fixSuggestions) {
    const rows = Object.entries(fixSuggestions).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`);
    if (rows.length > 0) blocks.push({ label: "修复建议", value: rows.join("；") });
  }
  return { chips, blocks };
};

const toReviewerCheckRows = (artifact: any) => {
  if (!artifact || typeof artifact !== "object" || !artifact.checks || typeof artifact.checks !== "object") {
    return [] as Array<{ name: string; status: string }>;
  }
  return Object.entries(artifact.checks).map(([k, v]) => ({
    name: reviewerCheckLabelMap[k] || k,
    status: String(v || "NA").toUpperCase()
  }));
};

const AgentDetailModal = ({ 
  agent, 
  state, 
  onClose 
}: { 
  agent: AgentConfig; 
  state: AgentState; 
  onClose: () => void 
}) => {
  const [sparklineData, setSparklineData] = useState<number[]>([]);

  useEffect(() => {
      const fetchData = async () => {
          try {
              const res = await MarketAPI.getKline("BTC/USDT", "1h", 24);
              if (res && res.length > 0) {
                  setSparklineData(res.map(k => k.close));
              }
          } catch (e) {
              console.error("Sparkline fetch error", e);
          }
      };
      fetchData();
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(2, 6, 23, 0.9)',
        backdropFilter: 'blur(4px)',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px'
      }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        style={{
            width: '100%',
            height: '100%',
            backgroundColor: '#0f172a',
            border: `1px solid ${agent.color}`,
            borderRadius: '16px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: `0 0 40px ${agent.color}20`
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div style={{ padding: '20px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#1e293b' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <PixelAvatar seed={agent.avatarSeed} size={56} />
                <div>
                    <h2 style={{ fontSize: '20px', fontWeight: '800', color: 'white' }}>{agent.name}</h2>
                    <span style={{ 
                        fontSize: '12px', 
                        backgroundColor: `${agent.color}20`, 
                        color: agent.color, 
                        padding: '2px 8px', 
                        borderRadius: '4px', 
                        fontWeight: 'bold',
                        border: `1px solid ${agent.color}40`
                    }}>
                        {agent.role}
                    </span>
                </div>
            </div>
            <button onClick={onClose} style={{ color: '#64748b', cursor: 'pointer', padding: '8px', borderRadius: '8px', backgroundColor: '#334155' }}>
                <X size={20} />
            </button>
        </div>

        {/* Modal Content - Chat Interface Style */}
        <div style={{ flex: 1, padding: '24px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Sparkline Visualization */}
            {sparklineData.length > 0 && <Sparkline data={sparklineData} color={agent.color} />}

            {/* Context/Input Bubble */}
            <div style={{ alignSelf: 'flex-start', maxWidth: '80%' }}>
                <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '4px', marginLeft: '4px' }}>INPUT CONTEXT</div>
                <div style={{ 
                    backgroundColor: '#1e293b', 
                    padding: '12px 16px', 
                    borderRadius: '16px 16px 16px 4px', 
                    color: '#cbd5e1',
                    border: '1px solid #334155'
                }}>
                    {state.currentInput || "Waiting for data..."}
                </div>
            </div>

            {/* Thinking Process */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '12px', padding: '0 12px' }}>
                 <div style={{ fontSize: '11px', color: '#64748b', textAlign: 'center', display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
                    <div style={{ height: '1px', flex: 1, backgroundColor: '#334155' }}></div>
                    THINKING PROCESS
                    <div style={{ height: '1px', flex: 1, backgroundColor: '#334155' }}></div>
                 </div>
                 
                 {state.logs.length === 0 ? (
                    <div style={{ textAlign: 'center', color: '#475569', fontStyle: 'italic', marginTop: '20px' }}>
                        Waiting for activation...
                    </div>
                 ) : (
                    state.logs.map((log, i) => {
                        const isDecisionLog = log.type === 'output' && (log.content.startsWith("DECISION:") || log.content.startsWith("PROPOSAL:"));
                        const parsed = parseDecisionFromContent(log.content);
                        const action = (log.artifact?.action as string | undefined) || (parsed.action as string | undefined);
                        const confidence = (typeof log.artifact?.confidence === 'number' ? Number(log.artifact.confidence).toFixed(2) : parsed.confidence) || undefined;
                        const rr = (log.artifact?.rr as string | undefined) || (parsed.r_r as string | undefined);
                        const entry = (log.artifact?.entry != null ? Number(log.artifact.entry).toFixed(2) : parsed.entry) || undefined;
                        const sl = (log.artifact?.sl != null ? Number(log.artifact.sl).toFixed(2) : parsed.sl) || undefined;
                        const tp = (log.artifact?.tp != null ? Number(log.artifact.tp).toFixed(2) : parsed.tp) || undefined;
                        const qty = (log.artifact?.quantity != null ? Number(log.artifact.quantity).toFixed(4) : parsed.qty) || undefined;
                        const decisionReasoning = typeof log.artifact?.reasoning === 'string' ? log.artifact.reasoning : (parsed.reason || "");
                        const genericBlocks: Array<{label: string, value: string}> = [];
                        const genericChips: string[] = [];
                        const reviewerCheckRows = !isDecisionLog && agent.id === "reviewer" ? toReviewerCheckRows(log.artifact) : [];
                        if (!isDecisionLog && log.type === 'output' && log.artifact) {
                            if (agent.id === "analyst") {
                                if (log.artifact.bias) genericChips.push(`偏向 ${String(log.artifact.bias)}`);
                                if (log.artifact.risk) genericBlocks.push({ label: "核心风险", value: String(log.artifact.risk) });
                                if (log.artifact.reasoning) genericBlocks.push({ label: "分析逻辑", value: String(log.artifact.reasoning) });
                            } else if (agent.id === "sentiment") {
                                if (typeof log.artifact.score === "number") genericChips.push(`情绪分 ${Number(log.artifact.score).toFixed(2)}`);
                                if (Array.isArray(log.artifact.drivers) && log.artifact.drivers.length > 0) genericBlocks.push({ label: "驱动因素", value: log.artifact.drivers.join("；") });
                            } else if (agent.id === "reviewer") {
                                const reviewer = toReviewerSections(log.artifact);
                                genericChips.push(...reviewer.chips);
                                genericBlocks.push(...reviewer.blocks);
                            } else if (agent.id === "reflector") {
                                if (log.artifact.status) genericChips.push(`状态 ${String(log.artifact.status)}`);
                                if (log.artifact.insight_preview) genericBlocks.push({ label: "记忆摘要", value: String(log.artifact.insight_preview) });
                            }
                        }
                        return (
                        <motion.div 
                            key={log.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.05 }}
                            style={{ 
                                display: 'flex', 
                                gap: '12px', 
                                alignItems: 'flex-start',
                                padding: '8px 12px',
                                borderRadius: '8px',
                                backgroundColor: log.type === 'output' ? `${agent.color}10` : 'transparent',
                                borderLeft: log.type === 'output' ? `2px solid ${agent.color}` : '2px solid transparent',
                                marginBottom: '4px'
                            }}
                        >
                            <span style={{ 
                                color: '#64748b', 
                                minWidth: '60px', 
                                fontSize: '10px', 
                                marginTop: '2px',
                                fontFamily: 'monospace',
                                display: 'flex',
                                flexDirection: 'column'
                            }}>
                                <span>{log.timestamp}</span>
                                {log.session_id && (
                                    <span 
                                        title={log.session_id} 
                                        style={{ 
                                            fontSize: '8px', 
                                            color: '#475569', 
                                            marginTop: '2px', 
                                            cursor: 'help',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap',
                                            maxWidth: '60px'
                                        }}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            navigator.clipboard.writeText(log.session_id || "");
                                        }}
                                    >
                                        {log.session_id}
                                    </span>
                                )}
                            </span>
                            <div style={{ flex: 1, overflow: 'hidden' }}>
                                {isDecisionLog && (
                                    <div style={{ marginBottom: '8px', padding: '10px', borderRadius: '8px', backgroundColor: '#0b1220', border: `1px solid ${agent.color}40` }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                            <div style={{ backgroundColor: `${agent.color}20`, color: agent.color, border: `1px solid ${agent.color}60`, borderRadius: '999px', padding: '2px 8px', fontSize: '10px', fontWeight: 'bold' }}>
                                                {actionLabelMap[action || ""] || action || "决策"}
                                            </div>
                                            {confidence && (
                                                <div style={{ backgroundColor: '#111827', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '999px', padding: '2px 8px', fontSize: '10px' }}>
                                                    置信度 {confidence}
                                                </div>
                                            )}
                                            {rr && (
                                                <div style={{ backgroundColor: '#111827', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '999px', padding: '2px 8px', fontSize: '10px' }}>
                                                    风险收益比 {rr}
                                                </div>
                                            )}
                                        </div>
                                        <div style={{ marginTop: '8px', display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: '6px' }}>
                                            {entry && <div style={{ fontSize: '11px', color: '#cbd5e1' }}>入场价: <span style={{ color: 'white' }}>{entry}</span></div>}
                                            {qty && <div style={{ fontSize: '11px', color: '#cbd5e1' }}>仓位: <span style={{ color: 'white' }}>{qty}</span></div>}
                                            {sl && <div style={{ fontSize: '11px', color: '#cbd5e1' }}>止损: <span style={{ color: 'white' }}>{sl}</span></div>}
                                            {tp && <div style={{ fontSize: '11px', color: '#cbd5e1' }}>止盈: <span style={{ color: 'white' }}>{tp}</span></div>}
                                        </div>
                                    </div>
                                )}
                                <span style={{ 
                                    color: log.type === 'output' ? '#e2e8f0' : '#94a3b8',
                                    fontWeight: log.type === 'output' ? 'bold' : 'normal',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                    display: isDecisionLog ? 'none' : 'inline'
                                }}>
                                    {log.content}
                                </span>
                                {!isDecisionLog && log.type === 'output' && genericChips.length > 0 && (
                                    <div style={{ marginTop: '8px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                        {genericChips.map((chip, idx) => (
                                            <div key={`${log.id}-chip-${idx}`} style={{ backgroundColor: '#111827', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '999px', padding: '2px 8px', fontSize: '10px' }}>
                                                {chip}
                                            </div>
                                        ))}
                                    </div>
                                )}
                                {!isDecisionLog && log.type === 'output' && genericBlocks.length > 0 && (
                                    <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                        {genericBlocks.slice(0, 3).map((item, idx) => (
                                            <div key={`${log.id}-generic-${idx}`} style={{ borderLeft: `2px solid ${agent.color}60`, paddingLeft: '8px' }}>
                                                <div style={{ fontSize: '10px', color: agent.color, fontWeight: 'bold' }}>{item.label}</div>
                                                <div style={{ fontSize: '11px', color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{item.value}</div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                {!isDecisionLog && log.type === 'output' && reviewerCheckRows.length > 0 && (
                                    <div style={{ marginTop: '8px', borderLeft: `2px solid ${agent.color}60`, paddingLeft: '8px' }}>
                                        <div style={{ fontSize: '10px', color: agent.color, fontWeight: 'bold' }}>规则检查表</div>
                                        <div style={{ marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                            {reviewerCheckRows.map((row, idx) => (
                                                <div key={`${log.id}-check-${idx}`} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                                                    <span style={{ color: '#cbd5e1' }}>{row.name}</span>
                                                    <span style={{ color: row.status === "PASS" ? '#22c55e' : row.status === "FAIL" ? '#ef4444' : '#eab308', fontWeight: 'bold' }}>{row.status}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {log.type === 'output' && parseReasoningBlocks(decisionReasoning).length > 0 && (
                                    <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                        {parseReasoningBlocks(decisionReasoning).map((item, idx) => (
                                            <div key={`${log.id}-${idx}`} style={{ borderLeft: `2px solid ${agent.color}60`, paddingLeft: '8px' }}>
                                                <div style={{ fontSize: '10px', color: agent.color, fontWeight: 'bold' }}>{reasoningLabelMap[item.label] || item.label}</div>
                                                <div style={{ fontSize: '11px', color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{item.value}</div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                {log.type === 'process' && log.content.includes("Step") && (
                                    <div style={{ height: '1px', backgroundColor: '#334155', margin: '8px 0', width: '100%' }} />
                                )}
                            </div>
                        </motion.div>
                    )})
                 )}
            </div>

            {/* Final Decision Bubble */}
            {state.currentOutput && (() => {
                const parsed = parseDecisionFromContent(state.currentOutput);
                const action = (state.artifact?.action as string | undefined) || (parsed.action as string | undefined);
                const confidence = (typeof state.artifact?.confidence === 'number' ? Number(state.artifact.confidence).toFixed(2) : parsed.confidence) || undefined;
                const rr = (state.artifact?.rr as string | undefined) || (parsed.r_r as string | undefined);
                const entry = (state.artifact?.entry != null ? Number(state.artifact.entry).toFixed(2) : parsed.entry) || undefined;
                const sl = (state.artifact?.sl != null ? Number(state.artifact.sl).toFixed(2) : parsed.sl) || undefined;
                const tp = (state.artifact?.tp != null ? Number(state.artifact.tp).toFixed(2) : parsed.tp) || undefined;
                const qty = (state.artifact?.quantity != null ? Number(state.artifact.quantity).toFixed(4) : parsed.qty) || undefined;
                const decisionReasoning = typeof state.artifact?.reasoning === 'string' ? state.artifact.reasoning : (parsed.reason || "");
                const reasoningBlocks = parseReasoningBlocks(decisionReasoning);
                const isDecisionOutput = state.currentOutput.startsWith("DECISION:") || state.currentOutput.startsWith("PROPOSAL:");
                const genericBlocks: Array<{label: string, value: string}> = [];
                const genericChips: string[] = [];
                const reviewerCheckRows = !isDecisionOutput && agent.id === "reviewer" ? toReviewerCheckRows(state.artifact) : [];
                if (!isDecisionOutput && state.artifact) {
                    if (agent.id === "analyst") {
                        if (state.artifact.bias) genericChips.push(`偏向 ${String(state.artifact.bias)}`);
                        if (state.artifact.risk) genericBlocks.push({ label: "核心风险", value: String(state.artifact.risk) });
                        if (state.artifact.reasoning) genericBlocks.push({ label: "分析逻辑", value: String(state.artifact.reasoning) });
                    } else if (agent.id === "sentiment") {
                        if (typeof state.artifact.score === "number") genericChips.push(`情绪分 ${Number(state.artifact.score).toFixed(2)}`);
                        if (Array.isArray(state.artifact.drivers) && state.artifact.drivers.length > 0) genericBlocks.push({ label: "驱动因素", value: state.artifact.drivers.join("；") });
                    } else if (agent.id === "reviewer") {
                        const reviewer = toReviewerSections(state.artifact);
                        genericChips.push(...reviewer.chips);
                        genericBlocks.push(...reviewer.blocks);
                    } else if (agent.id === "reflector") {
                        if (state.artifact.status) genericChips.push(`状态 ${String(state.artifact.status)}`);
                        if (state.artifact.insight_preview) genericBlocks.push({ label: "记忆摘要", value: String(state.artifact.insight_preview) });
                    }
                }
                return (
                    <motion.div 
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        style={{ alignSelf: 'flex-end', maxWidth: '85%', width: '100%' }}
                    >
                        <div style={{ fontSize: '11px', color: agent.color, marginBottom: '6px', textAlign: 'right', marginRight: '4px' }}>FINAL DECISION</div>
                        <div style={{ 
                            backgroundColor: `${agent.color}18`, 
                            padding: '12px 14px', 
                            borderRadius: '12px', 
                            border: `1px solid ${agent.color}`,
                            boxShadow: `0 4px 12px ${agent.color}25`,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                <div style={{ backgroundColor: `${agent.color}20`, color: agent.color, border: `1px solid ${agent.color}70`, borderRadius: '999px', padding: '2px 8px', fontSize: '10px', fontWeight: 'bold' }}>
                                    {isDecisionOutput ? (actionLabelMap[action || ""] || action || "决策") : "输出摘要"}
                                </div>
                                {isDecisionOutput && confidence && <div style={{ backgroundColor: '#0b1220', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '999px', padding: '2px 8px', fontSize: '10px' }}>置信度 {confidence}</div>}
                                {isDecisionOutput && rr && <div style={{ backgroundColor: '#0b1220', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '999px', padding: '2px 8px', fontSize: '10px' }}>风险收益比 {rr}</div>}
                                {!isDecisionOutput && genericChips.map((chip, idx) => (
                                    <div key={`final-chip-${idx}`} style={{ backgroundColor: '#0b1220', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '999px', padding: '2px 8px', fontSize: '10px' }}>{chip}</div>
                                ))}
                            </div>
                            {isDecisionOutput && (
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: '6px' }}>
                                    {entry && <div style={{ fontSize: '11px', color: '#e2e8f0' }}>入场价: {entry}</div>}
                                    {qty && <div style={{ fontSize: '11px', color: '#e2e8f0' }}>仓位: {qty}</div>}
                                    {sl && <div style={{ fontSize: '11px', color: '#e2e8f0' }}>止损: {sl}</div>}
                                    {tp && <div style={{ fontSize: '11px', color: '#e2e8f0' }}>止盈: {tp}</div>}
                                </div>
                            )}
                            {isDecisionOutput && reasoningBlocks.length > 0 ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {reasoningBlocks.map((item, idx) => (
                                        <div key={`final-${idx}`} style={{ borderLeft: `2px solid ${agent.color}60`, paddingLeft: '8px' }}>
                                            <div style={{ fontSize: '10px', color: agent.color, fontWeight: 'bold' }}>{reasoningLabelMap[item.label] || item.label}</div>
                                            <div style={{ fontSize: '11px', color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{item.value}</div>
                                        </div>
                                    ))}
                                </div>
                            ) : isDecisionOutput ? (
                                <div style={{ fontSize: '11px', color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{state.currentOutput}</div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {genericBlocks.length > 0 ? genericBlocks.map((item, idx) => (
                                        <div key={`final-generic-${idx}`} style={{ borderLeft: `2px solid ${agent.color}60`, paddingLeft: '8px' }}>
                                            <div style={{ fontSize: '10px', color: agent.color, fontWeight: 'bold' }}>{item.label}</div>
                                            <div style={{ fontSize: '11px', color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{item.value}</div>
                                        </div>
                                    )) : (
                                        <div style={{ fontSize: '11px', color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{state.currentOutput}</div>
                                    )}
                                    {reviewerCheckRows.length > 0 && (
                                        <div style={{ borderLeft: `2px solid ${agent.color}60`, paddingLeft: '8px' }}>
                                            <div style={{ fontSize: '10px', color: agent.color, fontWeight: 'bold' }}>规则检查表</div>
                                            <div style={{ marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                                {reviewerCheckRows.map((row, idx) => (
                                                    <div key={`final-check-${idx}`} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                                                        <span style={{ color: '#cbd5e1' }}>{row.name}</span>
                                                        <span style={{ color: row.status === "PASS" ? '#22c55e' : row.status === "FAIL" ? '#ef4444' : '#eab308', fontWeight: 'bold' }}>{row.status}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </motion.div>
                );
            })()}
        </div>
      </motion.div>
    </motion.div>
  );
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// --- Portfolio Sidebar Component ---
const PortfolioSidebar = () => {
    const [positions, setPositions] = useState<Position[]>([]);
    const [balance, setBalance] = useState<number>(0);
    const [loading, setLoading] = useState(true);

    const fetchData = async () => {
        try {
            // Fetch Balance
            const balanceRes = await fetch(`${API_URL}/api/v1/trade/balance?currency=USDT`);
            if (balanceRes.ok) {
                const data = await balanceRes.json();
                setBalance(parseFloat(data.balance || 0));
            }

            // Fetch Positions
            const res = await fetch(`${API_URL}/api/v1/trade/positions`);
            if (res.ok) {
                const data = await res.json();
                
                // Enhance with current price and PnL
                const enhancedPositions = await Promise.all(data.map(async (pos: any) => {
                    let currentPrice = pos.entry_price; // Default
                    try {
                        // Fetch latest price for symbol
                        const klines = await MarketAPI.getKline(pos.symbol, "1m", 1);
                        if (klines && klines.length > 0) {
                            currentPrice = klines[klines.length - 1].close;
                        }
                    } catch (err) {
                        console.error(`Failed to fetch price for ${pos.symbol}`, err);
                    }

                    const quantity = pos.size || pos.quantity;
                    const isLong = pos.side.toUpperCase() === 'LONG' || pos.side.toUpperCase() === 'BUY';
                    
                    // PnL Calculation
                    let pnl = 0;
                    let pnlPercent = 0;
                    
                    if (isLong) {
                        pnl = (currentPrice - pos.entry_price) * quantity;
                        pnlPercent = ((currentPrice - pos.entry_price) / pos.entry_price) * 100;
                    } else {
                        pnl = (pos.entry_price - currentPrice) * quantity;
                        pnlPercent = ((pos.entry_price - currentPrice) / pos.entry_price) * 100;
                    }

                    return {
                        symbol: pos.symbol,
                        side: pos.side,
                        entry_price: pos.entry_price,
                        current_price: currentPrice,
                        quantity: quantity,
                        pnl: pnl, // Absolute PnL
                        pnl_percent: pnlPercent
                    };
                }));

                setPositions(enhancedPositions);
            }
        } catch (e) {
            console.error("Failed to fetch portfolio data", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000); // Poll every 5s
        return () => clearInterval(interval);
    }, []);

    return (
        <div style={{ 
            width: '280px', 
            borderLeft: '1px solid #1e293b', 
            backgroundColor: '#0f172a',
            display: 'flex',
            flexDirection: 'column'
        }}>
            <div style={{ padding: '12px', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Wallet size={16} className="text-blue-400" />
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#e2e8f0' }}>LIVE PORTFOLIO</span>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
                {loading ? (
                    <div style={{ textAlign: 'center', color: '#64748b', fontSize: '12px', marginTop: '20px' }}>Loading...</div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {/* Cash Position */}
                        <div style={{ 
                            backgroundColor: '#1e293b', 
                            borderRadius: '8px', 
                            padding: '10px',
                            border: '1px solid #334155'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                <span style={{ fontWeight: 'bold', fontSize: '13px', color: 'white' }}>USDT</span>
                                <span style={{ 
                                    fontSize: '11px', 
                                    fontWeight: 'bold', 
                                    color: '#94a3b8',
                                    backgroundColor: '#334155',
                                    padding: '2px 6px',
                                    borderRadius: '4px'
                                }}>
                                    CASH
                                </span>
                            </div>
                            
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ fontSize: '9px', textTransform: 'uppercase', color: '#94a3b8' }}>Available Balance</div>
                                <div style={{ color: '#22c55e', fontWeight: 'bold', fontFamily: 'monospace' }}>${balance.toLocaleString(undefined, {minimumFractionDigits: 2})}</div>
                            </div>
                        </div>

                        {/* Trade Positions */}
                        {positions.length === 0 && (
                            <div style={{ textAlign: 'center', color: '#64748b', fontSize: '12px', marginTop: '10px', fontStyle: 'italic' }}>
                                No open trades.
                            </div>
                        )}

                        {positions.map((pos, idx) => {
                            const isLong = pos.side.toUpperCase() === 'LONG' || pos.side.toUpperCase() === 'BUY';
                            const pnl = pos.pnl || 0;
                            const pnlPercent = pos.pnl_percent || 0;
                            const isProfit = pnl >= 0;

                            return (
                                <div key={idx} style={{ 
                                    backgroundColor: '#1e293b', 
                                    borderRadius: '8px', 
                                    padding: '10px',
                                    border: '1px solid #334155'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                        <span style={{ fontWeight: 'bold', fontSize: '13px', color: 'white' }}>{pos.symbol}</span>
                                        <span style={{ 
                                            fontSize: '11px', 
                                            fontWeight: 'bold', 
                                            color: isLong ? '#22c55e' : '#ef4444',
                                            backgroundColor: isLong ? '#22c55e20' : '#ef444420',
                                            padding: '2px 6px',
                                            borderRadius: '4px'
                                        }}>
                                            {pos.side}
                                        </span>
                                    </div>
                                    
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px', color: '#94a3b8' }}>
                                        <div>
                                            <div style={{ fontSize: '9px', textTransform: 'uppercase' }}>Entry</div>
                                            <div style={{ color: '#cbd5e1' }}>{pos.entry_price.toFixed(2)}</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: '9px', textTransform: 'uppercase' }}>Size</div>
                                            <div style={{ color: '#cbd5e1' }}>{pos.quantity}</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: '9px', textTransform: 'uppercase' }}>Current</div>
                                            <div style={{ color: '#cbd5e1' }}>{pos.current_price.toFixed(2)}</div>
                                        </div>
                                    </div>

                                    <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <span style={{ fontSize: '10px', color: '#64748b' }}>PnL</span>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: isProfit ? '#22c55e' : '#ef4444', fontWeight: 'bold', fontSize: '12px' }}>
                                            {isProfit ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                                            {pnl > 0 ? '+' : ''}{pnlPercent.toFixed(2)}% <span style={{fontSize: '10px', opacity: 0.8}}>(${pnl.toFixed(2)})</span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
            
            {/* Context Note */}
            <div style={{ padding: '12px', borderTop: '1px solid #1e293b', backgroundColor: '#0f172a' }}>
                 <div style={{ fontSize: '10px', color: '#64748b', display: 'flex', gap: '6px', alignItems: 'start' }}>
                    <AlertCircle size={12} style={{ marginTop: '1px', flexShrink: 0 }} />
                    <span>Positions are monitored by Reviewer Agent for risk management.</span>
                 </div>
            </div>
        </div>
    );
};


interface AgentThinkingCardProps {
    onSignalUpdate?: (signal: any) => void;
}

export const AgentThinkingCard = ({ onSignalUpdate }: AgentThinkingCardProps) => {
  const [agentsState, setAgentsState] = useState<Record<string, AgentState>>(() => {
    const initial: Record<string, AgentState> = {};
    AGENTS.forEach(a => {
        initial[a.id] = { status: 'idle', logs: [] };
    });
    return initial;
  });
  
  const [isLoopActive, setIsLoopActive] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  // Hydrate state from backend persistence
  useEffect(() => {
      const hydrate = async () => {
          try {
              // 1. Check Running Status
              const statusRes = await fetch(`${API_URL}/api/v1/workflow/runner/status`);
              if (statusRes.ok) {
                  const statusData = await statusRes.json();
                  // Force boolean conversion
                  const running = statusData.is_running === true;
                  
                  if (running !== isLoopActive) {
                      setIsLoopActive(running);
                  }

                  if (running) {
                      const symbol = statusData.symbol || "BTC/USDT";
                      // Only connect if not already connected or symbol changed
                      if (!eventSourceRef.current || !eventSourceRef.current.url.includes(encodeURIComponent(symbol))) {
                          connectMonitor(symbol);
                      }
                  } else {
                      if (eventSourceRef.current) {
                          console.log("Loop stopped, closing SSE.");
                          eventSourceRef.current.close();
                          eventSourceRef.current = null;
                      }
                  }
              }

              // 2. Load Latest Logs (Initial or Periodic Sync)
              // Only sync logs if we are NOT in active loop mode to avoid race conditions with SSE
              // OR if we have no logs at all
              const hasLogs = Object.values(agentsState).some(s => s.logs.length > 0);
              
              if (!isLoopActive || !hasLogs) {
                  const res = await fetch(`${API_URL}/api/v1/workflow/latest?symbol=BTC/USDT`);
                  if (res.ok) {
                      const data = await res.json();
                      if (data.session && data.session.logs.length > 0) {
                          const polledSessionId = data.session.id;
                          
                          setCurrentSessionId(prev => {
                              if (prev !== polledSessionId) {
                                  updateStateFromLogs(data.session.logs);
                                  return polledSessionId;
                              }
                              return prev;
                          });
                      }
                  }
              }
          } catch (e) {
              console.error("Hydration failed", e);
          }
      };

      hydrate();
      const interval = setInterval(hydrate, 5000);
      return () => clearInterval(interval);
  }, [isLoopActive]); // Re-run when active state changes

  const updateStateFromLogs = (logs: any[]) => {
      setAgentsState(prev => {
          const resetState: Record<string, AgentState> = {};
          AGENTS.forEach(a => { resetState[a.id] = { status: 'idle', logs: [] }; });
          
          logs.forEach((log: any) => {
              const agentId = log.agent_id;
              if (!resetState[agentId]) return;
              
              resetState[agentId].logs.push({
                  id: String(log.id),
                  timestamp: formatTime(log.timestamp),
                  session_id: log.session_id,
                  type: log.type,
                  content: log.content,
                  artifact: log.artifact
              });
              
              // ... (rest of state derivation) ...
              const looksLikeDecision = typeof log.content === 'string' && (log.content.startsWith("DECISION:") || log.content.startsWith("PROPOSAL:"));
              const effectiveType = looksLikeDecision ? 'output' : log.type;

              if (effectiveType === 'process') {
                  const logTime = new Date(log.timestamp).getTime();
                  const now = new Date().getTime();
                  if (now - logTime < 60000) {
                      resetState[agentId].status = 'working';
                  }
                  if (log.content.length < 60) resetState[agentId].currentInput = log.content;
              } else if (effectiveType === 'output') {
                  resetState[agentId].status = 'success';
                  resetState[agentId].currentOutput = log.content;
              }
              
              if (log.artifact) {
                  resetState[agentId].artifact = log.artifact;
              }
          });
          
          return resetState;
      });
  };

  const connectMonitor = (symbol: string) => {
      if (eventSourceRef.current) {
          eventSourceRef.current.close();
      }
      
      console.log("Connecting Monitor SSE to:", symbol);
      const evtSource = new EventSource(`/api/ai_engine/stream/monitor?symbol=${encodeURIComponent(symbol)}`);
      eventSourceRef.current = evtSource;

      evtSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            const agentId = data.agent_id;
            
            if (!agentId) return;

            // Notify parent if Analyst has artifact (Signal)
            if (agentId === 'analyst' && data.artifact) {
                onSignalUpdate?.(data.artifact);
            }

            // AUTO-CLEAR LOGIC: If session_id changes, clear logs
            setCurrentSessionId(prevId => {
                if (data.session_id && prevId && data.session_id !== prevId) {
                    console.log("Session changed! Clearing logs...", prevId, "->", data.session_id);
                    // Clear logs in state
                    setAgentsState(prev => {
                        const reset: Record<string, AgentState> = {};
                        AGENTS.forEach(a => { reset[a.id] = { status: 'idle', logs: [] }; });
                        return reset;
                    });
                    return data.session_id;
                }
                return data.session_id || prevId;
            });

            setAgentsState(prev => {
                const currentAgentState = prev[agentId] || { status: 'idle', logs: [] };
                
                let newStatus = currentAgentState.status;
                let newOutput = currentAgentState.currentOutput;
                let newInput = currentAgentState.currentInput;
                const newArtifact = data.artifact || currentAgentState.artifact;
                const looksLikeDecision = typeof data.content === 'string' && (data.content.startsWith("DECISION:") || data.content.startsWith("PROPOSAL:"));
                const effectiveType = looksLikeDecision ? 'output' : data.type;

                if (effectiveType === 'process' && data.content) {
                     newStatus = 'working';
                     if (!data.content.startsWith("Step") && data.content.length < 50) {
                         newInput = data.content;
                     }
                } else if (effectiveType === 'output') {
                    newStatus = 'success';
                    newOutput = data.content;
                }

                const newLogs = [...currentAgentState.logs, {
                    id: Math.random().toString(),
                    timestamp: formatTime(data.timestamp),
                    session_id: data.session_id, // Map session_id
                    type: effectiveType,
                    content: data.content,
                    artifact: data.artifact ?? null
                }];

                return {
                    ...prev,
                    [agentId]: {
                        ...currentAgentState,
                        status: newStatus,
                        currentOutput: newOutput,
                        currentInput: newInput,
                        artifact: newArtifact,
                        logs: newLogs
                    }
                };
            });

        } catch (e) {
            console.error("SSE Parse Error", e);
        }
    };

    evtSource.onerror = (err) => {
        console.error("EventSource failed:", err);
    };
  };

  const stopLoop = async () => {
      try {
          await fetch("/api/ai_engine/workflow/stop", { method: "POST" });
          setIsLoopActive(false);
          if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
          }
      } catch (e) {
          console.error("Stop failed", e);
      }
  };

  const deployAgents = async () => {
    setIsLoopActive(true);
    setErrorMessage(null);
    
    if (!isLoopActive) {
        // Fresh Start
        const reset: Record<string, AgentState> = {};
        AGENTS.forEach(a => { reset[a.id] = { status: 'idle', logs: [] }; });
        
        reset['analyst'] = {
            status: 'working',
            currentInput: 'Initiating Continuous Loop...',
            logs: [{
                id: 'init-log',
                timestamp: formatTime(new Date()),
                type: 'process',
                content: 'Connecting to Market Data Stream...'
            }]
        };
        
        setAgentsState(reset);
    } else {
        // Update Config Indication
        // Optional: Add log to UI
    }

    // Generate a unique session ID for each run to avoid "replay" of old logs
    const timestamp = Math.floor(Date.now() / 1000);
    const sessionId = `session_${timestamp}`;
    
    // Update local state to track this new session
    // Note: In a real app, we might want to store this ID in URL or context
    
    // In Continuous Mode, we connect to the MONITOR channel, not the specific session channel
    connectMonitor("BTC/USDT");

    try {
        const response = await fetch("/api/ai_engine/workflow/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                symbol: "BTC/USDT",
                session_id: sessionId
            })
        });
        
        if (!response.ok) throw new Error(`Server returned ${response.status}`);
        
    } catch (e) {
        console.error("Workflow trigger failed", e);
        setIsLoopActive(false);
        setErrorMessage(`Failed to deploy: ${String(e)}`);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: '#020617', color: '#e2e8f0', borderRadius: '12px', overflow: 'hidden', border: '1px solid #1e293b', position: 'relative' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', backgroundColor: '#0f172a', borderBottom: '1px solid #1e293b' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#94a3b8' }}>
          <Cpu size={16} />
          <span style={{ fontWeight: 'bold', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>AI Agent Swarm</span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {errorMessage && (
                <span style={{ fontSize: '12px', color: '#ef4444', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <AlertCircle size={14} /> {errorMessage}
                </span>
            )}
            
            {isLoopActive && (
                <button 
                    onClick={stopLoop}
                    style={{ 
                        padding: '6px', 
                        borderRadius: '4px', 
                        border: 'none', 
                        cursor: 'pointer', 
                        backgroundColor: '#ef4444', 
                        color: 'white',
                        display: 'flex',
                        alignItems: 'center'
                    }}
                    title="Stop Continuous Mode"
                >
                    <Square size={14} fill="currentColor" />
                </button>
            )}

            <button 
                onClick={deployAgents}
                style={{ 
                padding: '4px 12px', 
                borderRadius: '4px', 
                fontSize: '12px', 
                fontWeight: 'bold', 
                transition: 'all 0.2s', 
                border: 'none', 
                cursor: 'pointer', 
                backgroundColor: isLoopActive ? '#3b82f6' : '#4f46e5', 
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
                }}
            >
                {isLoopActive ? (
                    <>
                        <Play size={12} fill="currentColor" /> UPDATE CONFIG
                    </>
                ) : (
                    "START CONTINUOUS MODE"
                )}
            </button>
        </div>
      </div>

      {/* Main Content Area (Split View) */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* Left: Agent Grid */}
        <div style={{ flex: 1, padding: '16px', overflowY: 'auto' }}>
            <div style={{ 
                display: 'grid',
                gridTemplateColumns: '1fr 1fr', // 2x2 Layout
                gridAutoRows: 'minmax(200px, 1fr)', // Minimum height to prevent squash
                gap: '16px',
                height: '100%'
            }}>
                {AGENTS.map(agent => (
                    <AgentNode 
                        key={agent.id} 
                        config={agent} 
                        state={agentsState[agent.id]} 
                        onClick={() => setSelectedAgentId(agent.id)}
                    />
                ))}
            </div>
        </div>

        {/* Right: Portfolio Sidebar */}
        <PortfolioSidebar />

      </div>

      {/* Detail Modal */}
      <AnimatePresence>
        {selectedAgentId && (
            <AgentDetailModal 
                agent={AGENTS.find(a => a.id === selectedAgentId)!}
                state={agentsState[selectedAgentId]}
                onClose={() => setSelectedAgentId(null)}
            />
        )}
      </AnimatePresence>

    </div>
  );
};
