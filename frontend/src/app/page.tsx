"use client";

import MarketChartFeature from '@/features/market-chart/MarketChartFeature';
import { MarketOverview } from '@/components/dashboard/MarketOverview';
import { SideNav } from '@/components/layout/SideNav';
import { 
  Bell, 
  BrainCircuit,
  Newspaper,
  LayoutDashboard
} from 'lucide-react';
import { MarketAPI } from '@/lib/api/market';
import { useEffect, useRef, useState } from 'react';

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

export default function DashboardPage() {
  const [marketData, setMarketData] = useState<MarketOverviewData | null>(null);
  const [newsList, setNewsList] = useState<NewsItemData[]>([]);
  const [totalBalance, setTotalBalance] = useState<number>(0);
  const [latestIndicators, setLatestIndicators] = useState<LatestIndicators | null>(null);
  const [latestKlineTime, setLatestKlineTime] = useState<number | null>(null);
  const newsSeededRef = useRef(false);

  // Poll basic market data
  useEffect(() => {
    const fetchMarket = async () => {
      try {
        // Fetch Balance
        try {
            const balanceRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/trade/balance?currency=USDT`);
            if (balanceRes.ok) {
                const balanceData = await balanceRes.json();
                let equity = parseFloat(balanceData.balance || 0);
                
                const posRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/trade/positions`);
                if (posRes.ok) {
                    const positions = await posRes.json();
                    positions.forEach((p: any) => {
                        const val = (p.size || p.quantity) * p.entry_price; 
                        equity += val;
                    });
                }
                setTotalBalance(equity);
            }
        } catch (e) {
            console.error("Balance fetch error", e);
        }

        // Fetch News
        try {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
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

        // Fetch latest price
        const latestKlines = await MarketAPI.getKline("BTC/USDT", "1m", 1);
        let currentPrice = 0;
        let volume = 0;
        
        if (latestKlines && latestKlines.length > 0) {
            const latest = latestKlines[latestKlines.length - 1];
            currentPrice = latest.close;
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

        // Fetch 24h change
        const dailyKlines = await MarketAPI.getKline("BTC/USDT", "1d", 2);
        let change = 0;
        let high = 0;
        let low = 0;

        if (dailyKlines && dailyKlines.length > 0) {
          const latestDay = dailyKlines[dailyKlines.length - 1];
          const prevDay = dailyKlines.length > 1 ? dailyKlines[dailyKlines.length - 2] : latestDay;
          
          change = prevDay.close ? ((currentPrice - prevDay.close) / prevDay.close) * 100 : 0;
          high = latestDay.high;
          low = latestDay.low;
          if (latestDay.volume > volume) volume = latestDay.volume;
        }
        
        if (currentPrice > 0) {
            setMarketData({
                price: currentPrice,
                change24h: change,
                volume: volume,
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
  }, []);

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
              <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400">v1.0.0</span>
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
          
          {/* Top Section: Chart (Reduced Height) */}
          <div className="h-[45vh] min-h-[300px] flex gap-4">
             <div className="flex-1 bg-slate-900 rounded-xl border border-slate-800 overflow-hidden flex flex-col">
                <MarketChartFeature symbol="BTC/USDT" />
             </div>
             <IndicatorsCard indicators={latestIndicators} latestKlineTime={latestKlineTime} />
          </div>

          {/* Bottom Section: Overview & News */}
          <div className="flex-1 flex gap-4 min-h-[300px]">
             {/* Left: Market Overview */}
             <div className="w-1/3 flex flex-col gap-4">
                <MarketOverview marketData={marketData} signal={null} />
             </div>
             
             {/* Right: News Feed */}
             <div className="flex-1 overflow-hidden">
                <NewsCard news={newsList} />
             </div>
          </div>

        </div>
      </div>
    </div>
  );
}

const NewsCard = ({ news }: { news: NewsItemData[] }) => (
  <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 flex flex-col h-full">
    <div className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-2">
            <Newspaper size={16} className="text-blue-400" />
            <h2 className="text-sm font-bold text-slate-200">Market Intelligence</h2>
        </div>
        <span className="text-[10px] text-blue-500 bg-blue-900/20 px-2 py-0.5 rounded border border-blue-500/30">LIVE</span>
    </div>
    
    <div className="flex-1 overflow-y-auto flex flex-col gap-2 pr-1 custom-scrollbar">
        {news.length === 0 ? (
            <div className="text-center text-slate-500 text-xs mt-10">Loading news...</div>
        ) : (
            news.map((item, idx) => (
                <NewsItem 
                    key={idx}
                    title={item.title}
                    source={item.source}
                    time={new Date(item.published_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    sentiment={item.sentiment}
                    url={item.url}
                />
            ))
        )}
    </div>
  </div>
);

const IndicatorsCard = ({ indicators, latestKlineTime }: { indicators: LatestIndicators | null; latestKlineTime: number | null }) => (
  <div className="w-[280px] bg-slate-900 rounded-xl border border-slate-800 p-4 flex flex-col">
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

const NewsItem = ({ title, source, time, sentiment, url }: any) => (
    <a href={url} target="_blank" rel="noopener noreferrer" className="block decoration-0">
        <div className={`p-3 border-l-2 ${sentiment === 'Positive' ? 'border-green-500' : sentiment === 'Negative' ? 'border-red-500' : 'border-slate-500'} bg-slate-800/50 rounded-r-md hover:bg-slate-800 transition-colors`}>
            <div className="font-semibold text-xs text-slate-300 mb-1 leading-relaxed line-clamp-2">{title}</div>
            <div className="flex justify-between text-[10px] text-slate-500">
                <span className="font-bold text-slate-400">{source}</span>
                <span>{time}</span>
            </div>
        </div>
    </a>
);
