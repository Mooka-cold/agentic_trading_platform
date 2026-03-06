"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, TrendingUp, AlertTriangle, Activity } from "lucide-react";

interface MarketOverviewProps {
    marketData: any;
    signal: any;
}

export const MarketOverview = ({ marketData, signal }: MarketOverviewProps) => {
    const [isReasoningOpen, setIsReasoningOpen] = useState(true);

    const isBullish = signal?.bias === 'BULLISH';
    const isBearish = signal?.bias === 'BEARISH';
    
    return (
        <div style={{ 
            backgroundColor: '#0f172a', 
            borderRadius: '12px', 
            border: '1px solid #1e293b', 
            padding: '16px', 
            height: '100%', 
            display: 'flex', 
            flexDirection: 'column',
            color: '#e2e8f0',
            justifyContent: 'space-between'
        }}>
            {/* Header: Price & Signal */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0px' }}>
                <div>
                    <h2 style={{ fontSize: '14px', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase' }}>BTC/USDT</h2>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '4px' }}>
                        <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>
                            ${marketData?.price?.toLocaleString(undefined, {minimumFractionDigits: 2}) || '0.00'}
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '4px' }}>
                         <div style={{ fontSize: '12px', color: (marketData?.change24h || 0) >= 0 ? '#22c55e' : '#ef4444', fontWeight: 'bold' }}>
                            {(marketData?.change24h || 0) >= 0 ? '+' : ''}{(marketData?.change24h || 0).toFixed(2)}%
                        </div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>
                            Vol: ${(marketData?.volume || 0).toLocaleString()}
                        </div>
                    </div>
                </div>
                
                {/* AI Signal Badge (Enhanced) */}
                <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '4px', fontWeight: 'bold', letterSpacing: '0.5px' }}>AI SIGNAL</div>
                    <div style={{ 
                        backgroundColor: isBullish ? '#22c55e' : isBearish ? '#ef4444' : '#475569',
                        color: 'white',
                        padding: '8px 16px',
                        borderRadius: '8px',
                        fontWeight: '800',
                        fontSize: '14px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '8px',
                        boxShadow: isBullish ? '0 0 15px rgba(34, 197, 94, 0.4)' : isBearish ? '0 0 15px rgba(239, 68, 68, 0.4)' : 'none',
                        border: '1px solid rgba(255,255,255,0.1)'
                    }}>
                        <Activity size={16} />
                        {signal?.bias || 'NEUTRAL'} 
                        <span style={{ opacity: 0.8, fontSize: '12px', marginLeft: '4px', borderLeft: '1px solid rgba(255,255,255,0.3)', paddingLeft: '8px' }}>
                            {Math.round((signal?.confidence || 0) * 100)}%
                        </span>
                    </div>
                </div>
            </div>

            {/* Collapsible Reasoning */}
            <div style={{ marginTop: '16px', borderTop: '1px solid #1e293b', paddingTop: '12px' }}>
                <button 
                    onClick={() => setIsReasoningOpen(!isReasoningOpen)}
                    style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '6px', 
                        fontSize: '11px', 
                        color: '#64748b', 
                        fontWeight: 'bold', 
                        background: 'none', 
                        border: 'none', 
                        cursor: 'pointer', 
                        marginBottom: '8px',
                        padding: 0
                    }}
                >
                    {isReasoningOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    AI REASONING
                </button>
                
                {isReasoningOpen && (
                    <div style={{ 
                        padding: '12px', 
                        backgroundColor: '#1e293b50', 
                        borderRadius: '6px', 
                        fontSize: '12px', 
                        color: '#cbd5e1', 
                        lineHeight: '1.6',
                        borderLeft: '3px solid #3b82f6',
                        maxHeight: '120px',
                        overflowY: 'auto'
                    }}>
                        {signal?.reasoning || "AI Analyst is processing market data..."}
                    </div>
                )}
            </div>
        </div>
    );
};
