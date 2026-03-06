"use client";

import { useState, useEffect } from "react";
import MarketChartFeature from "@/features/market-chart/MarketChartFeature";
import { TrendingUp, TrendingDown, Activity, RefreshCw } from "lucide-react";
import { SignalsAPI, Signal } from "@/lib/api/signals";
import { motion } from "framer-motion";

export const MarketCard = () => {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [signal, setSignal] = useState<Signal | null>(null);
  const [loadingSignal, setLoadingSignal] = useState(false);

  useEffect(() => {
    const fetchSignal = async () => {
      setLoadingSignal(true);
      const data = await SignalsAPI.getLatest(symbol);
      setSignal(data);
      setLoadingSignal(false);
    };
    fetchSignal();
    const interval = setInterval(fetchSignal, 60000);
    return () => clearInterval(interval);
  }, [symbol]);

  const getSignalColor = (action: string) => {
    if (action === 'BUY') return { bg: '#dcfce7', text: '#166534' };
    if (action === 'SELL') return { bg: '#fee2e2', text: '#991b1b' };
    return { bg: '#f1f5f9', text: '#475569' };
  };

  const signalStyle = signal ? getSignalColor(signal.action) : { bg: '#f1f5f9', text: '#475569' };

  return (
    <>
      <div style={{ padding: '16px', borderBottom: '1px solid #f1f5f9', fontWeight: '700', fontSize: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#1e293b' }}>
        <span>Market Overview</span>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {loadingSignal && (
              <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}>
                <RefreshCw size={14} color="#9ca3af" />
              </motion.div>
            )}
            <span style={{ fontSize: '12px', color: '#64748b' }}>{symbol}</span>
        </div>
      </div>
      
      <div style={{ padding: '0', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Stat Row */}
        <div style={{ display: 'flex', padding: '16px', gap: '24px', borderBottom: '1px solid #f1f5f9' }}>
          <div>
            <label style={{ fontSize: '12px', color: '#64748b', display: 'block', marginBottom: '4px' }}>AI Signal</label>
            <div style={{ fontSize: '14px', backgroundColor: signalStyle.bg, color: signalStyle.text, padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              {signal ? (
                  <>
                    {signal.action === 'BUY' ? <TrendingUp size={14} /> : signal.action === 'SELL' ? <TrendingDown size={14} /> : <Activity size={14} />}
                    {signal.action} ({signal.confidence})
                  </>
              ) : (
                  "ANALYZING..."
              )}
            </div>
          </div>
          <div style={{ flex: 1 }}>
             <label style={{ fontSize: '12px', color: '#64748b', display: 'block', marginBottom: '4px' }}>Reasoning</label>
             <p style={{ fontSize: '12px', color: '#334155', lineHeight: '1.4', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {signal?.reasoning || "AI is analyzing market data..."}
             </p>
          </div>
        </div>
        
        {/* Chart Area */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <MarketChartFeature symbol={symbol} onSymbolChange={setSymbol} />
        </div>
      </div>
    </>
  );
};
