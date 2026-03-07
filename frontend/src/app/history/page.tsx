"use client";

import { SideNav } from "@/components/layout/SideNav";
import { useEffect, useState } from "react";
import { formatTime, formatDateTime } from "@/lib/utils";
import { 
  History, 
  ChevronRight, 
  ChevronDown, 
  Database, 
  Newspaper, 
  Activity,
  Cpu,
  ArrowRight,
  Download,
  Trash2,
  Trash
} from "lucide-react";

interface WorkflowSession {
  id: string;
  symbol?: string;
  status: string;
  start_time: string;
  end_time?: string;
  action?: string | null;
  review_status?: string | null; // New field
  duration_seconds?: number;
  log_count?: number;
}

interface WorkflowLog {
  id: number;
  session_id: string;
  agent_id: string;
  type: "input" | "process" | "output";
  content: string;
  timestamp: string;
  artifact?: any;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const formatDuration = (seconds?: number) => {
  if (!seconds || seconds <= 0) return "0s";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

export default function HistoryPage() {
  const [sessions, setSessions] = useState<WorkflowSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [logs, setLogs] = useState<WorkflowLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterSymbol, setFilterSymbol] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterAction, setFilterAction] = useState("");
  const [filterReviewStatus, setFilterReviewStatus] = useState(""); // New State
  const [filterProfit, setFilterProfit] = useState<boolean | null>(null);
  const selectedSession = sessions.find((session) => session.id === selectedSessionId) || null;

  const handleDownloadSession = () => {
    if (!selectedSessionId) return;
    const payload = {
      session: {
        ...selectedSession,
        id: selectedSessionId,
      },
      logs,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const safeSymbol = (selectedSession?.symbol || "session").replace(/[^\w\-]+/g, "_");
    link.href = url;
    link.download = `${safeSymbol}_${selectedSessionId.slice(0, 8)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Delete this session?")) return;
    
    try {
      const res = await fetch(`${API_URL}/api/v1/workflow/session/${id}`, { method: "DELETE" });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== id));
        if (selectedSessionId === id) setSelectedSessionId(null);
      }
    } catch (err) {
      console.error("Delete failed", err);
    }
  };

  const handleCleanupFailed = async () => {
    if (!confirm("Delete all FAILED sessions? This cannot be undone.")) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/workflow/sessions/cleanup`, { method: "DELETE" });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.status !== "FAILED"));
      }
    } catch (err) {
      console.error("Cleanup failed", err);
    }
  };

  // Fetch Sessions
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const params = new URLSearchParams();
        params.set("limit", "20");
        if (filterSymbol.trim()) params.set("symbol", filterSymbol.trim());
        if (filterStatus) params.set("status", filterStatus);
        if (filterAction) params.set("action", filterAction);
        if (filterReviewStatus) params.set("review_status", filterReviewStatus); // New Param
        if (filterProfit !== null) params.set("has_profit", filterProfit.toString());
        
        const res = await fetch(`${API_URL}/api/v1/workflow/history?${params.toString()}`);
        if (res.ok) {
          const data = await res.json();
          const list = Array.isArray(data) ? data : (Array.isArray(data?.history) ? data.history : []);
          setSessions(list);
          if (list.length > 0) {
            setSelectedSessionId((prev) => (prev && list.some((x: WorkflowSession) => x.id === prev) ? prev : list[0].id));
          } else {
            setSelectedSessionId(null);
            setLogs([]);
          }
        }
      } catch (e) {
        console.error("Failed to fetch history", e);
      }
    };
    fetchSessions();
  }, [filterSymbol, filterStatus, filterAction, filterReviewStatus, filterProfit]);

  // Fetch Logs for Selected Session
  useEffect(() => {
    if (!selectedSessionId) return;
    
    const fetchLogs = async () => {
      setLoading(true);
      setLogs([]); // Clear logs before fetching
      try {
        const encodedId = encodeURIComponent(selectedSessionId);
        const res = await fetch(`${API_URL}/api/v1/workflow/session/${encodedId}`);
        if (res.ok) {
          const data = await res.json();
          const session = data?.session;
          if (session?.symbol) {
            setSessions(prev => prev.map(s => s.id === session.id ? { ...s, symbol: session.symbol } : s));
          }
          setLogs(Array.isArray(session?.logs) ? session.logs : []);
        } else {
            console.warn(`Failed to fetch logs for ${selectedSessionId}: ${res.status}`);
        }
      } catch (e) {
        console.error("Failed to fetch session details", e);
      } finally {
        setLoading(false);
      }
    };
    fetchLogs();
  }, [selectedSessionId]);

  return (
    <div className="flex h-screen bg-[#020617] text-slate-200 overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-[80px] min-w-[80px] border-r border-slate-800 bg-slate-900 flex flex-col items-center py-5 z-20">
        <SideNav />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-b border-slate-800 flex items-center px-6 bg-slate-900 shrink-0">
           <div className="flex items-center gap-3">
              <History className="text-blue-500" />
              <span className="font-bold text-lg">Decision History</span>
           </div>
        </header>

        <div className="flex flex-1 overflow-hidden">
          {/* Session List (Left) */}
          <div className="w-80 border-r border-slate-800 bg-slate-900 overflow-y-auto">
            <div className="p-4 border-b border-slate-800 font-bold text-sm text-slate-400 uppercase tracking-wider flex justify-between items-center">
              <span>Recent Sessions</span>
              <button 
                onClick={handleCleanupFailed}
                title="Clean all FAILED sessions"
                className="p-1 hover:text-red-400 text-slate-600 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
            <div className="p-3 border-b border-slate-800 space-y-2">
              <input
                value={filterSymbol}
                onChange={(e) => setFilterSymbol(e.target.value)}
                placeholder="Symbol: BTC/USDT"
                className="w-full bg-[#020617] border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 outline-none focus:border-blue-500"
              />
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="bg-[#020617] border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 outline-none focus:border-blue-500"
                >
                  <option value="">All Status</option>
                  <option value="RUNNING">RUNNING</option>
                  <option value="COMPLETED">COMPLETED</option>
                  <option value="FAILED">FAILED</option>
                </select>
                <select
                  value={filterAction}
                  onChange={(e) => setFilterAction(e.target.value)}
                  className="bg-[#020617] border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 outline-none focus:border-blue-500"
                >
                  <option value="">All Action</option>
                  <option value="BUY">BUY</option>
                  <option value="SELL">SELL</option>
                  <option value="HOLD">HOLD</option>
                  <option value="CLOSE">CLOSE</option>
                </select>
                <select
                  value={filterProfit === null ? "" : filterProfit.toString()}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === "true") setFilterProfit(true);
                    else if (val === "false") setFilterProfit(false);
                    else setFilterProfit(null);
                  }}
                  className="bg-[#020617] border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 outline-none focus:border-blue-500"
                >
                  <option value="">All PnL</option>
                  <option value="true">Profitable</option>
                  <option value="false">Loss/None</option>
                </select>
                <select
                  value={filterReviewStatus}
                  onChange={(e) => setFilterReviewStatus(e.target.value)}
                  className="bg-[#020617] border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 outline-none focus:border-blue-500"
                >
                  <option value="">All Review</option>
                  <option value="APPROVED">APPROVED</option>
                  <option value="REJECTED">REJECTED</option>
                  <option value="SKIPPED">SKIPPED</option>
                </select>
              </div>
            </div>
            {Array.isArray(sessions) && sessions.map(session => (
              <div 
                key={session.id}
                onClick={() => setSelectedSessionId(session.id)}
                className={`p-4 border-b border-slate-800 cursor-pointer hover:bg-slate-800 transition-colors group ${selectedSessionId === session.id ? 'bg-slate-800 border-l-4 border-l-blue-500' : 'border-l-4 border-l-transparent'}`}
              >
                <div className="flex justify-between items-center mb-1">
                  <span className="font-bold text-white">{session.symbol || "BTC/USDT"}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${session.status === 'COMPLETED' ? 'bg-green-900 text-green-300' : session.status === 'FAILED' ? 'bg-red-900 text-red-300' : 'bg-blue-900 text-blue-300'}`}>
                        {session.status}
                    </span>
                    <button
                        onClick={(e) => handleDeleteSession(e, session.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-opacity"
                        title="Delete Session"
                    >
                        <Trash size={12} />
                    </button>
                  </div>
                </div>
                <div className="text-xs text-slate-500">
                  {formatDateTime(session.start_time)}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Duration: {formatDuration(session.duration_seconds)}
                </div>
                <div className="text-xs text-slate-500">
                  Logs: {session.log_count ?? 0}
                </div>
                {session.action && (
                  <div className="text-xs mt-1 font-semibold flex items-center gap-2">
                    <span className={session.action === 'BUY' ? 'text-green-400' : session.action === 'SELL' ? 'text-red-400' : 'text-purple-300'}>
                        {session.action}
                    </span>
                    {session.review_status && (
                        <span className={`px-1 rounded text-[10px] border ${
                            session.review_status === 'APPROVED' ? 'border-green-800 text-green-500' : 
                            session.review_status === 'REJECTED' ? 'border-red-800 text-red-500' : 'border-slate-700 text-slate-500'
                        }`}>
                            {session.review_status}
                        </span>
                    )}
                  </div>
                )}
                <div className="text-xs text-slate-600 mt-1 font-mono truncate">
                  ID: {session.id.slice(0, 8)}...
                </div>
              </div>
            ))}
          </div>

          {/* Decision Chain (Right) */}
          <div className="flex-1 bg-[#020617] overflow-y-auto p-8">
            {loading ? (
              <div className="flex items-center justify-center h-full text-slate-500">Loading details...</div>
            ) : logs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-slate-500">Select a session to view details</div>
            ) : (
              <div className="max-w-4xl mx-auto space-y-8">
                <div className="text-center mb-8">
                  <h2 className="text-2xl font-bold text-white mb-2">Decision Chain Analysis</h2>
                  <div className="flex items-center justify-center gap-4 text-slate-500 text-sm">
                    <span>Session ID: {selectedSessionId}</span>
                    <button
                      onClick={handleDownloadSession}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors"
                    >
                      <Download size={12} />
                      下载 Session
                    </button>
                  </div>
                </div>

                {/* Group logs by Agent to show flow */}
                <ChainView logs={logs} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const ChainView = ({ logs }: { logs: WorkflowLog[] }) => {
  // Simple grouping logic: Sequential flow
  // We just map logs but style them based on type
  return (
    <div className="relative border-l-2 border-slate-800 ml-4 space-y-8 pb-12">
      {logs.map((log, idx) => (
        <div key={log.id} className="relative pl-8">
          {/* Timeline Dot */}
          <div className={`absolute -left-[9px] top-0 w-4 h-4 rounded-full border-2 ${getAgentColor(log.agent_id)} bg-[#020617]`} />
          
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-5 shadow-lg">
            {/* Header */}
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center gap-2">
                <AgentBadge id={log.agent_id} />
                <span className="text-xs text-slate-500 font-mono">{formatTime(log.timestamp)}</span>
              </div>
              <span className={`text-xs font-bold px-2 py-1 rounded uppercase ${getTypeColor(log.type)}`}>
                {log.type}
              </span>
            </div>

            {/* Content */}
            <div className="text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed mb-4">
              {log.content}
            </div>

            {/* Artifacts (Data Source, Indicators, News) */}
            {log.artifact && (
              <div className="mt-4 pt-4 border-t border-slate-800">
                <div className="text-xs font-bold text-slate-500 uppercase mb-2 flex items-center gap-2">
                  <Database size={12} /> Context Data & Artifacts
                </div>
                <div className="bg-[#020617] rounded-lg p-3 overflow-x-auto">
                  <ArtifactViewer artifact={log.artifact} />
                </div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

const ArtifactViewer = ({ artifact }: { artifact: any }) => {
  if (typeof artifact !== 'object') return <span>{String(artifact)}</span>;

  // Special handling for common artifact types
  
  // 1. Market Data Snapshot
  if (artifact.market_data) {
    const md = artifact.market_data;
    return (
      <div className="grid grid-cols-2 gap-4 text-xs">
        <div>
          <span className="text-slate-500 block">Price</span>
          <span className="text-green-400 font-mono font-bold">${md.price}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Volume</span>
          <span className="text-slate-300 font-mono">{md.volume}</span>
        </div>
        {md.indicators && (
          <div className="col-span-2 mt-2">
            <span className="text-slate-500 block mb-1">Indicators</span>
            <div className="flex gap-2 flex-wrap">
              {Object.entries(md.indicators).map(([k, v]: any) => (
                <span key={k} className="bg-slate-800 px-2 py-1 rounded border border-slate-700 font-mono text-blue-300">
                  {k}: {typeof v === 'number' ? v.toFixed(2) : v}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // 2. News/Sentiment
  if (artifact.news_analysis) {
    return (
      <div className="text-xs">
         <div className="mb-3 flex items-center justify-between">
            <div>
                <span className="text-slate-500 mr-2">Sentiment Score:</span>
                <span className={`font-bold ${artifact.score >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {artifact.score}
                </span>
            </div>
            <div className="text-[10px] text-slate-600">
                Based on {artifact.news_analysis.length} recent articles
            </div>
         </div>
         
         {/* Key Drivers */}
         {artifact.drivers && artifact.drivers.length > 0 && (
             <div className="mb-3 p-2 bg-slate-800/50 rounded border border-slate-800">
                 <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">Key Drivers</div>
                 <ul className="list-disc list-inside space-y-0.5">
                     {artifact.drivers.map((d: string, i: number) => (
                         <li key={i} className="text-slate-300">{d}</li>
                     ))}
                 </ul>
             </div>
         )}

         <div className="space-y-2 max-h-60 overflow-y-auto pr-1 custom-scrollbar">
           {artifact.news_analysis.map((n: any, i: number) => (
             <div key={i} className="group flex gap-3 items-start p-2 rounded hover:bg-slate-800/50 transition-colors border border-transparent hover:border-slate-800">
               <Newspaper size={14} className="mt-0.5 text-slate-600 group-hover:text-blue-500 transition-colors" />
               <div className="flex-1 min-w-0">
                 <div className="text-slate-300 leading-snug truncate group-hover:whitespace-normal group-hover:overflow-visible group-hover:text-white transition-all duration-200">
                    {n.title}
                 </div>
                 <div className="flex justify-between items-center mt-1">
                    <div className="text-[10px] text-slate-500 flex gap-2">
                        <span className="text-slate-400">{n.domain || n.source?.title || 'Unknown'}</span>
                        <span>•</span>
                        <span>{n.published_at ? new Date(n.published_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}</span>
                    </div>
                    {n.votes && (
                        <div className="flex gap-2 text-[10px]">
                            {n.votes.positive > 0 && <span className="text-green-600">↑{n.votes.positive}</span>}
                            {n.votes.negative > 0 && <span className="text-red-600">↓{n.votes.negative}</span>}
                        </div>
                    )}
                 </div>
               </div>
             </div>
           ))}
         </div>
      </div>
    );
  }

  // Default JSON view
  return (
    <pre className="text-xs text-slate-400 font-mono">
      {JSON.stringify(artifact, null, 2)}
    </pre>
  );
};

const getAgentColor = (id: string) => {
  switch(id) {
    case 'analyst': return 'border-blue-500';
    case 'strategist': return 'border-purple-500';
    case 'reviewer': return 'border-red-500';
    case 'executor': return 'border-green-500';
    default: return 'border-slate-500';
  }
};

const getTypeColor = (type: string) => {
  switch(type) {
    case 'input': return 'bg-slate-800 text-slate-400';
    case 'process': return 'bg-blue-900/30 text-blue-400';
    case 'output': return 'bg-green-900/30 text-green-400';
    default: return 'bg-slate-800 text-slate-400';
  }
};

const AgentBadge = ({ id }: { id: string }) => {
  const config: any = {
    analyst: { color: 'text-blue-400', bg: 'bg-blue-900/20', icon: <Activity size={14} />, label: 'The Analyst' },
    strategist: { color: 'text-purple-400', bg: 'bg-purple-900/20', icon: <Cpu size={14} />, label: 'The Strategist' },
    reviewer: { color: 'text-red-400', bg: 'bg-red-900/20', icon: <Database size={14} />, label: 'The Reviewer' },
    executor: { color: 'text-green-400', bg: 'bg-green-900/20', icon: <ArrowRight size={14} />, label: 'Executor' },
  };

  const c = config[id] || { color: 'text-slate-400', bg: 'bg-slate-800', icon: <Cpu size={14} />, label: id };

  return (
    <div className={`flex items-center gap-2 px-2 py-1 rounded-md ${c.bg} ${c.color} font-bold text-xs`}>
      {c.icon}
      {c.label}
    </div>
  );
};
