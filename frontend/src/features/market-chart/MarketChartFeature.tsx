"use client";

import { useKlines } from "@/hooks/useKlines";
import { KlineChart } from "@/components/ui/KlineChart";
import { useState } from "react";

interface MarketChartProps {
  symbol: string;
  onSymbolChange?: (newSymbol: string) => void;
}

export default function MarketChartFeature({ symbol, onSymbolChange }: MarketChartProps) {
  const [interval, setInterval] = useState("1m");
  const { data, loading, error } = useKlines(symbol, interval);

  if (error) return <div className="text-red-500">Error: {error}</div>;

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
            <option value="BTC/USDT">BTC/USDT</option>
            <option value="ETH/USDT">ETH/USDT</option>
            <option value="SOL/USDT">SOL/USDT</option>
            <option value="BNB/USDT">BNB/USDT</option>
          </select>
        </div>
      </div>
      
      {loading && data.length === 0 ? (
        <div className="flex items-center justify-center h-full text-slate-500 text-sm">Loading market data...</div>
      ) : (
        <div className="flex-1 w-full min-h-0 relative">
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
        </div>
      )}
    </div>
  );
}
