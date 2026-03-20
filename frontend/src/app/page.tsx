"use client";

import MarketChartFeature from '@/features/market-chart/MarketChartFeature';
import { MarketOverview } from '@/components/dashboard/MarketOverview';
import { SideNav } from '@/components/layout/SideNav';
import { 
  Bell, 
  BrainCircuit,
  Newspaper,
  LayoutDashboard,
  Activity,
  ShieldAlert,
  Save,
  RotateCcw,
  Gauge,
  Siren,
  ListTree
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useMarketTicker } from '@/hooks/useMarketTicker';

// --- Types ---
interface MarketOverviewData {
  price: number;
  change24h: number;
  volume: number;
  high24h: number;
  low24h: number;
}

interface NewsItemData {
  id: string;
  title: string;
  source: string;
  published_at: string;
  sentiment: string;
  url: string;
}
interface LatestIndicators {
  rsi: { value: number | null; calcTime: number | null };
  macd: { value: number | null; calcTime: number | null };
  macdSignal: { value: number | null; calcTime: number | null };
  macdHist: { value: number | null; calcTime: number | null };
  ma20: { value: number | null; calcTime: number | null };
  ma50: { value: number | null; calcTime: number | null };
  sma7: { value: number | null; calcTime: number | null };
  sma25: { value: number | null; calcTime: number | null };
  ema7: { value: number | null; calcTime: number | null };
  ema25: { value: number | null; calcTime: number | null };
  bbUpper: { value: number | null; calcTime: number | null };
  bbMiddle: { value: number | null; calcTime: number | null };
  bbLower: { value: number | null; calcTime: number | null };
  atr14: { value: number | null; calcTime: number | null };
}

interface RiskStateData {
  allowed: boolean;
  is_locked: boolean;
  lock_reason: string | null;
  current_equity: number;
  daily_start_balance: number;
  high_watermark: number;
  daily_dd: number;
  max_dd: number;
  daily_loss_limit_pct: number;
  max_drawdown_limit_pct: number;
}

interface SentimentAggregateData {
  score: number;
  confidence: number;
  news_score: number;
  fng_score: number;
  drivers: string[];
  conflicts: string[];
  source_breakdown: Record<string, number>;
  sample_count: number;
  raw_sample_count: number;
  quality_sample_count: number;
  dedup_removed_count: number;
  should_aggregate: boolean;
  trigger_reason: string;
  urgent_event: boolean;
  trade_gate: string;
}

interface InterpretationData {
  news_id: string;
  source: string;
  published_at: string;
  bias: string;
  magnitude: number;
  confidence: number;
  severity: string;
  final_status: string;
  summary_cn: string;
  assets: Array<string | { symbol?: string; confidence?: number }>;
}

type InterpretationScope = "symbol" | "all";

interface SentimentMonitorData {
  window_hours: number;
  total_interpreted: number;
  quality_interpreted: number;
  major_event_count: number;
  avg_confidence: number;
  dedup_removed_count: number;
  major_event_confidence_floor: number;
  quality_confidence_floor: number;
  severity_distribution: Record<string, number>;
  final_status_distribution: Record<string, number>;
  queue_status_distribution: Record<string, number>;
}

export default function DashboardPage() {
  const [marketData, setMarketData] = useState<MarketOverviewData | null>(null);
  const [newsList, setNewsList] = useState<NewsItemData[]>([]);
  const [totalBalance, setTotalBalance] = useState<number>(0);
  const [latestIndicators, setLatestIndicators] = useState<LatestIndicators | null>(null);
  const [latestKlineTime, setLatestKlineTime] = useState<number | null>(null);
  const [riskState, setRiskState] = useState<RiskStateData | null>(null);
  const [dailyLossLimit, setDailyLossLimit] = useState("15");
  const [maxDdLimit, setMaxDdLimit] = useState("15");
  const [riskSaving, setRiskSaving] = useState(false);
  const [sentimentAggregate, setSentimentAggregate] = useState<SentimentAggregateData | null>(null);
  const [interpretations, setInterpretations] = useState<InterpretationData[]>([]);
  const [allInterpretations, setAllInterpretations] = useState<InterpretationData[]>([]);
  const [sentimentMonitor, setSentimentMonitor] = useState<SentimentMonitorData | null>(null);
  const [interpretationScope, setInterpretationScope] = useState<InterpretationScope>("symbol");
  const newsSeededRef = useRef(false);
  const [activeSymbol, setActiveSymbol] = useState("BTC/USDT");
  
  // Real-time Ticker Hook
  const ticker = useMarketTicker(activeSymbol);

  // Poll runner status to sync active symbol
  useEffect(() => {
      const checkStatus = async () => {
          try {
              const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
              const res = await fetch(`${apiBase}/api/v1/workflow/runner/status`);
              if (res.ok) {
                  const data = await res.json();
                  if (data.is_running && data.symbol && data.symbol !== activeSymbol) {
                      setActiveSymbol(data.symbol);
                  }
              }
          } catch (e) {
              console.error("Status check failed", e);
          }
      };
      checkStatus();
      const interval = setInterval(checkStatus, 10000); // Check every 10s
      return () => clearInterval(interval);
  }, [activeSymbol]);

  // Poll basic market data (Historical / Indicators)
  useEffect(() => {
    const fetchMarket = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        
        // 1. Fetch Indicators (still from Klines for now, or could use ticker if indicators are in redis)
        const latestKlinesRes = await fetch(`${apiBase}/api/v1/market/kline?symbol=${encodeURIComponent(activeSymbol)}&interval=1m&limit=1`);
        let latestKlines: any[] = [];
        if (latestKlinesRes.ok) {
            latestKlines = await latestKlinesRes.json();
        }
        
        let volume = 0;
        
        if (Array.isArray(latestKlines) && latestKlines.length > 0) {
            const latest = latestKlines[latestKlines.length - 1];
            volume = latest.volume;
            setLatestKlineTime(latest.time);
            setLatestIndicators({
                rsi: { value: latest.rsi ?? null, calcTime: latest.rsi_calc_time ?? latest.time },
                macd: { value: latest.macd ?? null, calcTime: latest.macd_calc_time ?? latest.time },
                macdSignal: { value: latest.macd_signal ?? null, calcTime: latest.macd_signal_calc_time ?? latest.time },
                macdHist: { value: latest.macd_hist ?? null, calcTime: latest.macd_hist_calc_time ?? latest.time },
                ma20: { value: latest.ma20 ?? null, calcTime: latest.ma20_calc_time ?? latest.time },
                ma50: { value: latest.ma50 ?? null, calcTime: latest.ma50_calc_time ?? latest.time },
                sma7: { value: latest.sma_7 ?? null, calcTime: latest.sma_7_calc_time ?? latest.time },
                sma25: { value: latest.sma_25 ?? null, calcTime: latest.sma_25_calc_time ?? latest.time },
                ema7: { value: latest.ema_7 ?? null, calcTime: latest.ema_7_calc_time ?? latest.time },
                ema25: { value: latest.ema_25 ?? null, calcTime: latest.ema_25_calc_time ?? latest.time },
                bbUpper: { value: latest.bb_upper ?? null, calcTime: latest.bb_upper_calc_time ?? latest.time },
                bbMiddle: { value: latest.bb_middle ?? null, calcTime: latest.bb_middle_calc_time ?? latest.time },
                bbLower: { value: latest.bb_lower ?? null, calcTime: latest.bb_lower_calc_time ?? latest.time },
                atr14: { value: latest.atr_14 ?? null, calcTime: latest.atr_14_calc_time ?? latest.time }
            });
        }

        // 2. Fetch News
        try {
            const newsRes = await fetch(`${apiBase}/api/v1/news?limit=10`);
            if (newsRes.ok) {
                const newsData = await newsRes.json();
                if (Array.isArray(newsData) && newsData.length === 0 && !newsSeededRef.current) {
                    newsSeededRef.current = true;
                    const seedRes = await fetch(`${apiBase}/api/v1/jobs/sync-news`, { method: "POST" });
                    if (seedRes.ok) {
                        const retryRes = await fetch(`${apiBase}/api/v1/news?limit=10`);
                        if (retryRes.ok) {
                            const retryData = await retryRes.json();
                            setNewsList(retryData);
                        }
                    }
                } else {
                    setNewsList(newsData);
                }
            }
        } catch (e) {
            console.error("News fetch error", e);
        }

        // Fetch 24h stats from kline as fallback for high/low
        const dailyKlinesRes = await fetch(`${apiBase}/api/v1/market/kline?symbol=${encodeURIComponent(activeSymbol)}&interval=1d&limit=2`);
        let dailyKlines: any[] = [];
        if (dailyKlinesRes.ok) {
            dailyKlines = await dailyKlinesRes.json();
        }
        
        let high = 0;
        let low = 0;

        if (Array.isArray(dailyKlines) && dailyKlines.length > 0) {
          const latestDay = dailyKlines[dailyKlines.length - 1];
          high = latestDay.high;
          low = latestDay.low;
        }
        
        // Update Market Data State
        // Priority: Real-time Ticker > Historical Kline
        if (ticker) {
             setMarketData({
                price: ticker.price,
                change24h: ticker.change24h,
                volume: volume, // Volume still from kline for now or ticker if available
                high24h: high,
                low24h: low
            });
        } else if (latestKlines && latestKlines.length > 0) {
             // Fallback
             const latest = latestKlines[latestKlines.length - 1];
             setMarketData({
                price: latest.close,
                change24h: 0,
                volume: latest.volume,
                high24h: high,
                low24h: low
            });
        }

      } catch (e) {
        console.error("Market fetch error", e);
      }
    };
    
    fetchMarket();
    const interval = setInterval(fetchMarket, 5000); 
    return () => clearInterval(interval);
  }, [activeSymbol]);

  // Separate Effect for Equity Calculation using Real-time Ticker
  useEffect(() => {
      const calcEquity = async () => {
        try {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            
            // Fetch real account balance/equity instead of just balance endpoint
            const accountRes = await fetch(`${apiBase}/api/v1/trade/paper/account`);
            if (accountRes.ok) {
                const accountData = await accountRes.json();
                setTotalBalance(parseFloat(accountData.equity || accountData.balance || 0));
            } else {
                // Fallback to old balance endpoint if paper account fails
                const balanceRes = await fetch(`${apiBase}/api/v1/trade/balance?currency=USDT`);
                if (balanceRes.ok) {
                    const balanceData = await balanceRes.json();
                    let equity = parseFloat(balanceData.balance || 0);
                    
                    const posRes = await fetch(`${apiBase}/api/v1/trade/positions`);
                    if (posRes.ok) {
                        const positions = await posRes.json();
                        
                        // Calculate PnL for each position
                        for (const p of positions) {
                             let posPrice = p.entry_price;
                             // Use Real-time Ticker Price if available and matching symbol
                             if (p.symbol === activeSymbol && ticker?.price) {
                                 posPrice = ticker.price;
                             }
                             
                             const size = p.size || p.quantity;
                             let pnl = 0;
                             if (p.side.toUpperCase() === 'LONG' || p.side.toUpperCase() === 'BUY') {
                                 pnl = (posPrice - p.entry_price) * size;
                             } else {
                                 pnl = (p.entry_price - posPrice) * size;
                             }
                             equity += pnl;
                        }
                    }
                    setTotalBalance(equity);
                }
            }
        } catch (e) {
            console.error("Balance calc error", e);
        }
      };
      
      if (ticker) {
          calcEquity();
      }
  }, [ticker, activeSymbol]);

  useEffect(() => {
    const fetchRiskState = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const res = await fetch(`${apiBase}/api/v1/trade/risk/state`);
        if (!res.ok) return;
        const data: RiskStateData = await res.json();
        setRiskState(data);
        setDailyLossLimit((data.daily_loss_limit_pct * 100).toFixed(2));
        setMaxDdLimit((data.max_drawdown_limit_pct * 100).toFixed(2));
      } catch (e) {
        console.error("Risk state fetch error", e);
      }
    };
    fetchRiskState();
    const timer = setInterval(fetchRiskState, 10000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const fetchIntelligence = async () => {
      try {
        const [aggRes, interpRes, interpAllRes, monitorRes] = await Promise.all([
          fetch(`/api/ai_engine/sentiment/aggregate?symbol=${encodeURIComponent(activeSymbol)}`),
          fetch(`/api/ai_engine/sentiment/interpretations?symbol=${encodeURIComponent(activeSymbol)}&limit=40&scope=symbol`),
          fetch(`/api/ai_engine/sentiment/interpretations?symbol=${encodeURIComponent(activeSymbol)}&limit=80&scope=all`),
          fetch(`/api/ai_engine/sentiment/monitor?hours=24`)
        ]);
        if (aggRes.ok) {
          const aggData = await aggRes.json();
          setSentimentAggregate(aggData);
        }
        if (interpRes.ok) {
          const interpData = await interpRes.json();
          if (Array.isArray(interpData)) {
            setInterpretations(interpData);
          }
        }
        if (interpAllRes.ok) {
          const interpAllData = await interpAllRes.json();
          if (Array.isArray(interpAllData)) {
            setAllInterpretations(interpAllData);
          }
        }
        if (monitorRes.ok) {
          const monitorData = await monitorRes.json();
          setSentimentMonitor(monitorData);
        }
      } catch (e) {
        console.error("Sentiment intelligence fetch error", e);
      }
    };
    fetchIntelligence();
    const timer = setInterval(fetchIntelligence, 10000);
    return () => clearInterval(timer);
  }, [activeSymbol]);

  const saveRiskConfig = async () => {
    setRiskSaving(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const payload = {
        daily_loss_limit_pct: Number(dailyLossLimit) / 100,
        max_drawdown_limit_pct: Number(maxDdLimit) / 100
      };
      const res = await fetch(`${apiBase}/api/v1/trade/risk/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const updated = await res.json();
        setRiskState(updated);
        setDailyLossLimit((updated.daily_loss_limit_pct * 100).toFixed(2));
        setMaxDdLimit((updated.max_drawdown_limit_pct * 100).toFixed(2));
      } else {
        alert("风控参数保存失败");
      }
    } catch (e) {
      alert("风控参数保存失败");
    } finally {
      setRiskSaving(false);
    }
  };

  const resetDailyRisk = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${apiBase}/api/v1/trade/risk/reset-daily`, { method: "POST" });
      if (!res.ok) {
        alert("重置失败");
        return;
      }
      const stateRes = await fetch(`${apiBase}/api/v1/trade/risk/state`);
      if (stateRes.ok) {
        const state = await stateRes.json();
        setRiskState(state);
      }
    } catch (e) {
      alert("重置失败");
    }
  };

  return (
    <div className="flex h-screen bg-[#020617] text-white overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-[80px] min-w-[80px] border-r border-slate-800 bg-slate-900 flex flex-col items-center py-5 z-20">
        <SideNav />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* Top Bar */}
        <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900 shrink-0">
           <div className="flex items-center gap-3">
              <LayoutDashboard className="text-blue-500" />
              <span className="font-bold text-lg">Market Dashboard</span>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400">v1.1.0 (Real-time)</span>
           </div>
           
           <div className="flex items-center gap-5">
              <div className="text-right mr-3">
                  <div className="text-[10px] text-slate-400 uppercase font-bold">Est. Equity</div>
                  <div className="text-sm font-bold text-green-500">${totalBalance.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
              </div>
              <Bell size={20} className="text-gray-400 cursor-pointer hover:text-white" />
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-sm font-bold">
                HY
              </div>
           </div>
        </header>

        {/* Dashboard Grid */}
        <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
          
          <div className="h-[34vh] min-h-[250px] grid grid-cols-12 gap-4">
             <div className="col-span-7 bg-slate-900 rounded-xl border border-slate-800 overflow-hidden flex flex-col">
                <MarketChartFeature symbol={activeSymbol} onSymbolChange={setActiveSymbol} />
             </div>
             <div className="col-span-3">
               <TickerOrderBookCard ticker={ticker} />
             </div>
             <div className="col-span-2 flex flex-col gap-4">
                <MarketOverview marketData={marketData} signal={null} symbol={activeSymbol} />
             </div>
          </div>

          <div className="flex-1 flex gap-4 min-h-[420px]">
             <div className="w-[280px] flex flex-col gap-4">
                <RiskControlCard
                  riskState={riskState}
                  dailyLossLimit={dailyLossLimit}
                  maxDdLimit={maxDdLimit}
                  onDailyLossLimitChange={setDailyLossLimit}
                  onMaxDdLimitChange={setMaxDdLimit}
                  onSave={saveRiskConfig}
                  onResetDaily={resetDailyRisk}
                  saving={riskSaving}
                />
                <div className="overflow-hidden flex-1 min-h-[260px]">
                  <IndicatorsCard indicators={latestIndicators} latestKlineTime={latestKlineTime} />
                </div>
             </div>
             <div className="flex-1 overflow-hidden">
                <NewsCard
                  news={newsList}
                  interpretations={interpretations}
                  allInterpretations={allInterpretations}
                  aggregate={sentimentAggregate}
                  monitor={sentimentMonitor}
                  interpretationScope={interpretationScope}
                  onScopeChange={setInterpretationScope}
                />
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const TickerOrderBookCard = ({ ticker }: { ticker: any }) => {
    if (!ticker) return null;
    const bid = Number(ticker.bid || 0);
    const ask = Number(ticker.ask || 0);
    const bidQty = Number(ticker.bid_qty || 0);
    const askQty = Number(ticker.ask_qty || 0);
    const price = Number(ticker.price || 0);
    const spread = Number(ticker.spread ?? Math.abs(ask - bid));
    const spreadPct = Number(ticker.spread_pct ?? (price > 0 ? (spread / price) * 100 : 0));
    const bids: [number, number][] = Array.isArray(ticker.bids) ? ticker.bids : [];
    const asks: [number, number][] = Array.isArray(ticker.asks) ? ticker.asks : [];
    const bidDepthQty = Number(ticker.bid_depth_qty || 0);
    const askDepthQty = Number(ticker.ask_depth_qty || 0);
    const depthImbalance = Number(ticker.depth_imbalance || 0);
    const imbalanceText = depthImbalance > 0 ? "买盘偏强" : depthImbalance < 0 ? "卖盘偏强" : "均衡";
    
    return (
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 flex flex-col gap-2">
            <div className="flex items-center gap-2 mb-1">
                <Activity size={16} className="text-purple-400" />
                <h2 className="text-sm font-bold text-slate-200">Ticker + OrderBook</h2>
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="bg-red-900/10 border border-red-900/30 rounded p-2">
                    <div className="text-red-400 font-bold mb-1">Ask (Sell)</div>
                    <div className="flex justify-between">
                        <span className="text-slate-300">{ask.toFixed(2)}</span>
                        <span className="text-slate-500">{askQty.toFixed(4)}</span>
                    </div>
                </div>
                <div className="bg-green-900/10 border border-green-900/30 rounded p-2">
                    <div className="text-green-400 font-bold mb-1">Bid (Buy)</div>
                    <div className="flex justify-between">
                        <span className="text-slate-300">{bid.toFixed(2)}</span>
                        <span className="text-slate-500">{bidQty.toFixed(4)}</span>
                    </div>
                </div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-[10px]">
                <div className="bg-slate-800/50 border border-slate-700 rounded p-2">
                    <div className="text-slate-400">TopN买量</div>
                    <div className="text-green-300">{bidDepthQty.toFixed(3)}</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700 rounded p-2">
                    <div className="text-slate-400">TopN卖量</div>
                    <div className="text-red-300">{askDepthQty.toFixed(3)}</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700 rounded p-2">
                    <div className="text-slate-400">深度倾斜</div>
                    <div className={`${depthImbalance >= 0 ? "text-green-300" : "text-red-300"}`}>{(depthImbalance * 100).toFixed(1)}% {imbalanceText}</div>
                </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-[10px]">
                <div className="bg-slate-800/30 border border-red-900/20 rounded p-2">
                    <div className="text-red-300 mb-1">Top Asks</div>
                    <div className="space-y-0.5">
                        {asks.slice(0, 5).map((row, idx) => (
                            <div key={`ask-${idx}`} className="flex justify-between text-slate-300">
                                <span>{Number(row[0]).toFixed(2)}</span>
                                <span>{Number(row[1]).toFixed(4)}</span>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="bg-slate-800/30 border border-green-900/20 rounded p-2">
                    <div className="text-green-300 mb-1">Top Bids</div>
                    <div className="space-y-0.5">
                        {bids.slice(0, 5).map((row, idx) => (
                            <div key={`bid-${idx}`} className="flex justify-between text-slate-300">
                                <span>{Number(row[0]).toFixed(2)}</span>
                                <span>{Number(row[1]).toFixed(4)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
            
            <div className="flex justify-between text-[10px] text-slate-500 px-1 mt-1">
                <span>Spread: {spread.toFixed(2)} ({spreadPct.toFixed(4)}%)</span>
                <span>Depth: {(ticker.levels || 0)} levels</span>
            </div>
        </div>
    );
}

const NewsCard = ({
  news,
  interpretations,
  allInterpretations,
  aggregate,
  monitor,
  interpretationScope,
  onScopeChange
}: {
  news: NewsItemData[];
  interpretations: InterpretationData[];
  allInterpretations: InterpretationData[];
  aggregate: SentimentAggregateData | null;
  monitor: SentimentMonitorData | null;
  interpretationScope: InterpretationScope;
  onScopeChange: (scope: InterpretationScope) => void;
}) => (
  <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 flex flex-col h-full">
    <div className="flex justify-between items-center mb-3 shrink-0">
        <div className="flex items-center gap-2">
            <Newspaper size={16} className="text-blue-400" />
            <h2 className="text-sm font-bold text-slate-200">Market Intelligence</h2>
        </div>
        <span className="text-[10px] text-blue-500 bg-blue-900/20 px-2 py-0.5 rounded border border-blue-500/30">LIVE</span>
    </div>
    <div className="mb-3 shrink-0 flex items-center gap-2 text-[10px]">
      <button
        onClick={() => onScopeChange("symbol")}
        className={`px-2 py-1 rounded border ${interpretationScope === "symbol" ? "border-blue-500/60 bg-blue-900/30 text-blue-300" : "border-slate-700 bg-slate-800/40 text-slate-400"}`}
      >
        当前币种视图
      </button>
      <button
        onClick={() => onScopeChange("all")}
        className={`px-2 py-1 rounded border ${interpretationScope === "all" ? "border-blue-500/60 bg-blue-900/30 text-blue-300" : "border-slate-700 bg-slate-800/40 text-slate-400"}`}
      >
        全量视图
      </button>
    </div>
    <div className="grid grid-cols-3 gap-3 text-[11px] mb-3 shrink-0">
      <div className="bg-slate-800/40 border border-slate-800 rounded-md p-2">
        <div className="flex items-center gap-1 text-slate-400 mb-1"><Gauge size={12} />Aggregate</div>
        <div className="text-slate-200">Score: {aggregate ? aggregate.score.toFixed(3) : "—"}</div>
        <div className="text-slate-400">Gate: <span className="text-slate-200">{aggregate?.trade_gate || "—"}</span></div>
        <div className="text-slate-400">Quality/Dedup: <span className="text-slate-200">{aggregate ? `${aggregate.quality_sample_count}/${aggregate.sample_count}` : "—"}</span></div>
        <div className="text-slate-400">Trigger: <span className="text-slate-200">{aggregate?.trigger_reason || "—"}</span></div>
      </div>
      <div className="bg-slate-800/40 border border-slate-800 rounded-md p-2">
        <div className="flex items-center gap-1 text-slate-400 mb-1"><Siren size={12} />Major Event</div>
        <div className="text-slate-200">24h Count: {monitor ? monitor.major_event_count : "—"}</div>
        <div className="text-slate-400">Interpreted: <span className="text-slate-200">{monitor ? monitor.total_interpreted : "—"}</span></div>
        <div className="text-slate-400">Quality: <span className="text-slate-200">{monitor ? monitor.quality_interpreted : "—"}</span></div>
        <div className="text-slate-400">Avg Conf: <span className="text-slate-200">{monitor ? monitor.avg_confidence.toFixed(2) : "—"}</span></div>
      </div>
      <div className="bg-slate-800/40 border border-slate-800 rounded-md p-2">
        <div className="flex items-center gap-1 text-slate-400 mb-1"><ListTree size={12} />Severity Dist</div>
        <div className="text-slate-400">critical: <span className="text-red-300">{monitor?.severity_distribution?.critical || 0}</span></div>
        <div className="text-slate-400">high: <span className="text-amber-300">{monitor?.severity_distribution?.high || 0}</span></div>
        <div className="text-slate-400">dedup removed: <span className="text-slate-200">{monitor?.dedup_removed_count || 0}</span></div>
      </div>
    </div>
    <div className="text-[11px] text-slate-400 mb-2 shrink-0">
      最近聚合驱动: {aggregate?.drivers?.length ? aggregate.drivers.slice(0, 2).join(" | ") : "暂无"}
    </div>
    <div className="flex-1 overflow-y-auto flex flex-col gap-2 pr-1 custom-scrollbar min-h-0">
        {news.length === 0 ? (
            <div className="text-center text-slate-500 text-xs mt-10">Loading news...</div>
        ) : (
            news.map((item, idx) => (
                (() => {
                  const symbolViewInterpretation = interpretations.find((x) => x.news_id === item.id) || null;
                  const allViewInterpretation = allInterpretations.find((x) => x.news_id === item.id) || null;
                  const displayInterpretation = interpretationScope === "all" ? allViewInterpretation : symbolViewInterpretation;
                  let interpretationState: "ok" | "non_symbol" | "none" = "none";
                  if (displayInterpretation) {
                    interpretationState = "ok";
                  } else if (allViewInterpretation) {
                    interpretationState = "non_symbol";
                  }
                  return (
                <NewsItem
                    key={idx}
                    title={item.title}
                    source={item.source}
                    time={new Date(item.published_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    sentiment={item.sentiment}
                    url={item.url}
                    interpretation={displayInterpretation}
                    interpretationState={interpretationState}
                />
                  );
                })()
            ))
        )}
        {interpretations.length > 0 && news.length === 0 &&
          interpretations.map((item, idx) => (
                <NewsItem 
                    key={`interp-${idx}`}
                    title={item.summary_cn || "Interpreted item"}
                    source={item.source}
                    time={new Date(item.published_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    sentiment={item.bias}
                    url="#"
                    interpretation={item}
                />
            ))
        }
    </div>
  </div>
);

const RiskControlCard = ({
  riskState,
  dailyLossLimit,
  maxDdLimit,
  onDailyLossLimitChange,
  onMaxDdLimitChange,
  onSave,
  onResetDaily,
  saving
}: {
  riskState: RiskStateData | null;
  dailyLossLimit: string;
  maxDdLimit: string;
  onDailyLossLimitChange: (value: string) => void;
  onMaxDdLimitChange: (value: string) => void;
  onSave: () => void;
  onResetDaily: () => void;
  saving: boolean;
}) => (
  <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 flex flex-col gap-3">
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <ShieldAlert size={16} className="text-amber-400" />
        <h2 className="text-sm font-bold text-slate-200">Risk Control</h2>
      </div>
      <span className={`text-[10px] px-2 py-0.5 rounded border ${riskState?.is_locked ? 'text-red-400 border-red-500/30 bg-red-900/20' : 'text-green-400 border-green-500/30 bg-green-900/20'}`}>
        {riskState?.is_locked ? "LOCKED" : "ACTIVE"}
      </span>
    </div>
    <div className="grid grid-cols-2 gap-2 text-[11px]">
      <div className="bg-slate-800/40 border border-slate-800 rounded-md px-2 py-1.5">
        <div className="text-slate-400">Current Equity</div>
        <div className="text-slate-200 font-semibold">{riskState ? `$${riskState.current_equity.toFixed(2)}` : "—"}</div>
      </div>
      <div className="bg-slate-800/40 border border-slate-800 rounded-md px-2 py-1.5">
        <div className="text-slate-400">Daily DD</div>
        <div className={`font-semibold ${riskState && riskState.daily_dd < 0 ? 'text-red-400' : 'text-green-400'}`}>
          {riskState ? `${(riskState.daily_dd * 100).toFixed(2)}%` : "—"}
        </div>
      </div>
      <div className="bg-slate-800/40 border border-slate-800 rounded-md px-2 py-1.5">
        <div className="text-slate-400">Daily Start</div>
        <div className="text-slate-200 font-semibold">{riskState ? `$${riskState.daily_start_balance.toFixed(2)}` : "—"}</div>
      </div>
      <div className="bg-slate-800/40 border border-slate-800 rounded-md px-2 py-1.5">
        <div className="text-slate-400">Max DD</div>
        <div className={`font-semibold ${riskState && riskState.max_dd < 0 ? 'text-red-400' : 'text-green-400'}`}>
          {riskState ? `${(riskState.max_dd * 100).toFixed(2)}%` : "—"}
        </div>
      </div>
    </div>
    {riskState?.lock_reason && (
      <div className="text-[11px] text-red-300 bg-red-900/20 border border-red-800/40 rounded p-2">
        {riskState.lock_reason}
      </div>
    )}
    <div className="grid grid-cols-2 gap-2 text-[11px]">
      <div className="space-y-1">
        <label className="text-slate-400">Daily Loss Limit (%)</label>
        <input
          value={dailyLossLimit}
          onChange={(e) => onDailyLossLimitChange(e.target.value)}
          className="w-full bg-[#020617] border border-slate-700 rounded px-2 py-1 text-slate-200"
          placeholder="15"
        />
      </div>
      <div className="space-y-1">
        <label className="text-slate-400">Max Drawdown Limit (%)</label>
        <input
          value={maxDdLimit}
          onChange={(e) => onMaxDdLimitChange(e.target.value)}
          className="w-full bg-[#020617] border border-slate-700 rounded px-2 py-1 text-slate-200"
          placeholder="15"
        />
      </div>
    </div>
    <div className="flex gap-2">
      <button
        onClick={onSave}
        disabled={saving}
        className={`flex-1 px-3 py-2 rounded text-xs font-bold flex items-center justify-center gap-1 ${saving ? 'bg-slate-700 text-slate-300' : 'bg-blue-600 hover:bg-blue-700 text-white'}`}
      >
        <Save size={12} /> {saving ? "Saving..." : "Save"}
      </button>
      <button
        onClick={onResetDaily}
        className="flex-1 px-3 py-2 rounded text-xs font-bold bg-slate-700 hover:bg-slate-600 text-slate-200 flex items-center justify-center gap-1"
      >
        <RotateCcw size={12} /> Reset Daily
      </button>
    </div>
  </div>
);

const IndicatorsCard = ({ indicators, latestKlineTime }: { indicators: LatestIndicators | null; latestKlineTime: number | null }) => (
  <div className="h-full bg-slate-900 rounded-xl border border-slate-800 p-4 flex flex-col">
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        <BrainCircuit size={16} className="text-blue-400" />
        <h2 className="text-sm font-bold text-slate-200">Latest Indicators</h2>
      </div>
      <span className="text-[10px] text-blue-500 bg-blue-900/20 px-2 py-0.5 rounded border border-blue-500/30">1m</span>
    </div>
    <div className="text-[10px] text-slate-500 mb-3">
      最新K线时间: {latestKlineTime ? new Date(latestKlineTime * 1000).toLocaleString([], { hour: '2-digit', minute: '2-digit', month: '2-digit', day: '2-digit' }) : "—"}
    </div>
    {indicators ? (
      <div className="flex-1 grid grid-cols-2 gap-3 text-xs">
        <IndicatorRow label="RSI(14)" value={indicators.rsi.value} precision={2} timestamp={indicators.rsi.calcTime} />
        <IndicatorRow label="MACD" value={indicators.macd.value} precision={4} timestamp={indicators.macd.calcTime} />
        <IndicatorRow label="MACD Sig" value={indicators.macdSignal.value} precision={4} timestamp={indicators.macdSignal.calcTime} />
        <IndicatorRow label="MACD Hist" value={indicators.macdHist.value} precision={4} timestamp={indicators.macdHist.calcTime} />
        <IndicatorRow label="MA20" value={indicators.ma20.value} precision={2} timestamp={indicators.ma20.calcTime} />
        <IndicatorRow label="MA50" value={indicators.ma50.value} precision={2} timestamp={indicators.ma50.calcTime} />
        <IndicatorRow label="SMA7" value={indicators.sma7.value} precision={2} timestamp={indicators.sma7.calcTime} />
        <IndicatorRow label="SMA25" value={indicators.sma25.value} precision={2} timestamp={indicators.sma25.calcTime} />
        <IndicatorRow label="EMA7" value={indicators.ema7.value} precision={2} timestamp={indicators.ema7.calcTime} />
        <IndicatorRow label="EMA25" value={indicators.ema25.value} precision={2} timestamp={indicators.ema25.calcTime} />
        <IndicatorRow label="BB Upper" value={indicators.bbUpper.value} precision={2} timestamp={indicators.bbUpper.calcTime} />
        <IndicatorRow label="BB Mid" value={indicators.bbMiddle.value} precision={2} timestamp={indicators.bbMiddle.calcTime} />
        <IndicatorRow label="BB Lower" value={indicators.bbLower.value} precision={2} timestamp={indicators.bbLower.calcTime} />
        <IndicatorRow label="ATR14" value={indicators.atr14.value} precision={2} timestamp={indicators.atr14.calcTime} />
      </div>
    ) : (
      <div className="text-center text-slate-500 text-xs mt-10">Loading indicators...</div>
    )}
  </div>
);

const IndicatorRow = ({ label, value, precision, timestamp }: { label: string; value: number | null; precision: number; timestamp: number | null }) => {
  const displayValue = value == null ? "—" : Number(value).toFixed(precision);
  const timeLabel = timestamp ? new Date(timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "—";
  return (
  <div className="flex items-center justify-between bg-slate-800/40 border border-slate-800 rounded-md px-2 py-1.5">
    <span className="text-slate-400">{label}</span>
    <div className="flex flex-col items-end">
      <span className="text-slate-200 font-semibold">{displayValue}</span>
      <span className="text-[10px] text-slate-500">{timeLabel}</span>
    </div>
  </div>
  );
};

const NewsItem = ({ title, source, time, sentiment, url, interpretation, interpretationState }: any) => (
    <a href={url} target="_blank" rel="noopener noreferrer" className="block decoration-0">
        <div className={`p-3 border-l-2 ${sentiment === 'Positive' ? 'border-green-500' : sentiment === 'Negative' ? 'border-red-500' : 'border-slate-500'} bg-slate-800/50 rounded-r-md hover:bg-slate-800 transition-colors`}>
            <div className="font-semibold text-xs text-slate-300 mb-1 leading-relaxed line-clamp-2">{title}</div>
            <div className="flex justify-between text-[10px] text-slate-500">
                <span className="font-bold text-slate-400">{source}</span>
                <span>{time}</span>
            </div>
            {!interpretation && interpretationState === "non_symbol" && (
              <div className="mt-2 text-[10px] text-amber-300 bg-amber-900/20 border border-amber-800/40 rounded px-2 py-1">
                已解读（非当前币种相关）
              </div>
            )}
            {!interpretation && interpretationState === "none" && (
              <div className="mt-2 text-[10px] text-slate-400 bg-slate-800/60 border border-slate-700 rounded px-2 py-1">
                暂无解读结果
              </div>
            )}
            {interpretation && (
              <div className="mt-2 grid grid-cols-4 gap-2 text-[10px]">
                <span className="px-1.5 py-0.5 rounded bg-slate-700 text-slate-200">bias: {interpretation.bias}</span>
                <span className="px-1.5 py-0.5 rounded bg-slate-700 text-slate-200">sev: {interpretation.severity}</span>
                <span className="px-1.5 py-0.5 rounded bg-slate-700 text-slate-200">mag: {(Number(interpretation.magnitude || 0)).toFixed(2)}</span>
                <span className="px-1.5 py-0.5 rounded bg-slate-700 text-slate-200">conf: {(Number(interpretation.confidence || 0)).toFixed(2)}</span>
              </div>
            )}
            {interpretation?.summary_cn && (
              <div className="text-[10px] text-slate-400 mt-1 line-clamp-2">
                {interpretation.summary_cn}
              </div>
            )}
        </div>
    </a>
);
