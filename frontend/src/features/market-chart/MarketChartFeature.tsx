"use client";

import { useKlines } from "@/hooks/useKlines";
import { useMarketTicker } from "@/hooks/useMarketTicker";
import { useSecondSeries } from "@/hooks/useSecondSeries";
import { KlineChart } from "@/components/ui/KlineChart";
import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL } from "@/lib/api/base";

interface MarketChartProps {
  symbol: string;
  onSymbolChange?: (newSymbol: string) => void;
}

export default function MarketChartFeature({ symbol, onSymbolChange }: MarketChartProps) {
  const [interval, setInterval] = useState("1m");
  const [symbolOptions, setSymbolOptions] = useState<string[]>([]);
  const { data, loading, error } = useKlines(symbol, interval);
  const ticker = useMarketTicker(symbol);
  const secondSeries = useSecondSeries(symbol, 600);

  useEffect(() => {
    let cancelled = false;
    const fetchSymbols = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/market/symbols`);
        if (!res.ok) return;
        const payload = await res.json();
        if (!cancelled && Array.isArray(payload.symbols) && payload.symbols.length > 0) {
          setSymbolOptions(payload.symbols);
        }
      } catch (_) {
      }
    };
    fetchSymbols();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <div className="text-red-500">Error: {error}</div>;

  const spread = ticker ? Math.max(0, ticker.ask - ticker.bid) : 0;
  const spreadPct = ticker && ticker.price > 0 ? (spread / ticker.price) * 100 : 0;

  return (
    <div className="w-full h-full flex flex-col">
      <div className="flex justify-between items-center px-4 py-3 border-b border-slate-800 bg-slate-900">
        <h2 className="text-sm font-bold text-slate-200">MARKET CHART: {symbol}</h2>
        <div className="flex gap-2">
          <select 
            value={interval}
            onChange={(e) => setInterval(e.target.value)}
            className="p-1 text-xs border border-slate-700 rounded bg-slate-800 text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="1m">1m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
          </select>
          <select 
            value={symbol}
            onChange={(e) => onSymbolChange?.(e.target.value)}
            className="p-1 text-xs border border-slate-700 rounded bg-slate-800 text-slate-300 focus:outline-none focus:border-blue-500"
          >
            {symbolOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="px-4 py-2 border-b border-slate-800 bg-slate-900/80">
        <div className="flex items-center justify-between">
          <div className="flex items-end gap-3">
            <div className="text-2xl font-bold text-slate-100">
              {ticker?.price ? ticker.price.toFixed(2) : "—"}
            </div>
            <div className={`${(ticker?.change24h ?? 0) >= 0 ? "text-green-400" : "text-red-400"} text-sm font-semibold`}>
              {(ticker?.change24h ?? 0).toFixed(2)}%
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <div>Bid {ticker?.bid ? ticker.bid.toFixed(2) : "—"}</div>
            <div>Ask {ticker?.ask ? ticker.ask.toFixed(2) : "—"}</div>
            <div>Spread {spread.toFixed(2)} ({spreadPct.toFixed(4)}%)</div>
          </div>
        </div>
      </div>

      <div className="flex-1 w-full min-h-0 flex flex-col">
        <div className="flex-1 min-h-0 relative">
          {loading && data.length === 0 ? (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">Loading market data...</div>
          ) : (
            <KlineChart
              data={data}
              colors={{
                backgroundColor: '#0f172a',
                lineColor: '#3b82f6',
                textColor: '#94a3b8',
                areaTopColor: '#3b82f6',
                areaBottomColor: 'rgba(59, 130, 246, 0.1)',
              }}
            />
          )}
        </div>
        <SecondSeriesMiniChart points={secondSeries} />
      </div>
    </div>
  );
}

const SecondSeriesMiniChart = ({ points }: { points: { time: number; price: number }[] }) => {
  const chartPoints = useMemo(() => {
    if (!Array.isArray(points) || points.length < 2) {
      return "";
    }
    const width = 1000;
    const height = 120;
    const prices = points.map((p) => p.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    return points
      .map((p, idx) => {
        const x = (idx / (points.length - 1)) * width;
        const y = height - ((p.price - min) / range) * height;
        return `${x},${y}`;
      })
      .join(" ");
  }, [points]);

  const latestPrice = points.length > 0 ? points[points.length - 1].price : null;
  const timeLabels = useMemo(() => {
    if (!Array.isArray(points) || points.length === 0) {
      return null;
    }
    const formatTime = (ts: number) =>
      new Date(ts * 1000).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    const first = points[0];
    const middle = points[Math.floor(points.length / 2)];
    const last = points[points.length - 1];
    return {
      first: formatTime(first.time),
      middle: formatTime(middle.time),
      last: formatTime(last.time),
    };
  }, [points]);

  return (
    <div className="h-[140px] border-t border-slate-800 bg-slate-900/70 px-4 py-2">
      <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
        <span>最近10分钟秒级行情</span>
        <span>{latestPrice ? `实时 ${latestPrice.toFixed(2)}` : "连接中"}</span>
      </div>
      {chartPoints ? (
        <div className="h-[100px]">
          <svg viewBox="0 0 1000 120" className="w-full h-[84px]">
            <polyline
              fill="none"
              stroke="#22c55e"
              strokeWidth="2"
              points={chartPoints}
            />
          </svg>
          <div className="flex items-center justify-between text-[10px] text-slate-500 mt-1">
            <span>{timeLabels?.first ?? "—"}</span>
            <span>{timeLabels?.middle ?? "—"}</span>
            <span>{timeLabels?.last ?? "—"}</span>
          </div>
        </div>
      ) : (
        <div className="h-[100px] flex items-center justify-center text-xs text-slate-500">秒级数据加载中...</div>
      )}
    </div>
  );
};
