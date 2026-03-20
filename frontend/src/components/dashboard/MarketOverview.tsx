"use client";

import { useState, useEffect, useCallback } from "react";
import { ChevronDown, ChevronUp, Activity, Zap, Pause } from "lucide-react";

interface MarketOverviewProps {
    marketData: any;
    signal: any;
    symbol: string;
}

export const MarketOverview = ({ marketData, signal, symbol }: MarketOverviewProps) => {
    const [isReasoningOpen, setIsReasoningOpen] = useState(true);
    const [isRunning, setIsRunning] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [liveSignal, setLiveSignal] = useState<any>(null);
    const [liveReasoning, setLiveReasoning] = useState<string>("");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3201";

    // Fetch running status
    const checkStatus = useCallback(async () => {
        try {
            const res = await fetch(`${apiUrl}/api/v1/workflow/runner/status`);
            if (res.ok) {
                const data = await res.json();
                setIsRunning(Boolean(data.is_running));
            }
        } catch (e) {
            console.error("Status check failed", e);
        }
    }, [apiUrl]);

    useEffect(() => {
        checkStatus();
        const interval = setInterval(checkStatus, 2000);
        return () => clearInterval(interval);
    }, [checkStatus]);

    useEffect(() => {
        const streamSymbol = symbol || "BTC/USDT";
        const evtSource = new EventSource(`/api/ai_engine/stream/monitor?symbol=${encodeURIComponent(streamSymbol)}`);
        evtSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (!data || !data.agent_id || !data.content) return;
                const artifact = data.artifact && typeof data.artifact === "object" ? data.artifact : null;
                if (artifact) {
                    setLiveSignal((prev: any) => ({
                        ...(prev || {}),
                        ...artifact
                    }));
                }
                if (artifact?.reasoning && typeof artifact.reasoning === "string") {
                    setLiveReasoning(artifact.reasoning);
                } else {
                    const prefix = String(data.agent_id).toUpperCase();
                    setLiveReasoning(`${prefix}: ${String(data.content)}`);
                }
            } catch {
            }
        };
        evtSource.onerror = () => {
            evtSource.close();
        };
        return () => evtSource.close();
    }, [symbol]);

    const toggleWorkflow = async () => {
        setIsProcessing(true);
        try {
            const url = isRunning 
                ? `${apiUrl}/api/v1/workflow/stop`
                : `${apiUrl}/api/v1/workflow/run`;
            
            const method = "POST";
            const body = isRunning ? {} : { symbol: "BTC/USDT" };
            
            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            
            if (res.ok) {
                await checkStatus();
            } else {
                const errorText = await res.text();
                console.error("Toggle failed", errorText);
            }
        } catch (e) {
            console.error("Toggle failed", e);
        } finally {
            setIsProcessing(false);
        }
    };

    const displaySignal = liveSignal || signal;
    const displayReasoning = liveReasoning || displaySignal?.reasoning || "AI Analyst is processing market data...";
    const isBullish = displaySignal?.bias === 'BULLISH';
    const isBearish = displaySignal?.bias === 'BEARISH';
    
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
                
                {/* Control Button & Signal */}
                <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
                    
                    <button
                        onClick={toggleWorkflow}
                        disabled={isProcessing}
                        style={{
                            backgroundColor: isRunning ? '#ef4444' : '#3b82f6',
                            color: 'white',
                            border: 'none',
                            padding: '6px 12px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 'bold',
                            cursor: isProcessing ? 'wait' : 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            opacity: isProcessing ? 0.7 : 1,
                            boxShadow: isRunning ? '0 0 10px rgba(239, 68, 68, 0.3)' : '0 0 10px rgba(59, 130, 246, 0.3)'
                        }}
                    >
                        {isProcessing ? (
                            <span>...</span>
                        ) : isRunning ? (
                            <>
                                <Pause size={14} fill="currentColor" />
                                STOP AUTO
                            </>
                        ) : (
                            <>
                                <Zap size={14} fill="currentColor" />
                                START AUTO
                            </>
                        )}
                    </button>

                    <div style={{ 
                        backgroundColor: isBullish ? '#22c55e' : isBearish ? '#ef4444' : '#475569',
                        color: 'white',
                        padding: '6px 12px',
                        borderRadius: '6px',
                        fontWeight: '800',
                        fontSize: '12px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        boxShadow: isBullish ? '0 0 15px rgba(34, 197, 94, 0.2)' : isBearish ? '0 0 15px rgba(239, 68, 68, 0.2)' : 'none',
                        border: '1px solid rgba(255,255,255,0.1)'
                    }}>
                        <Activity size={14} />
                        {displaySignal?.bias || 'NEUTRAL'} 
                        <span style={{ opacity: 0.8, fontSize: '10px', marginLeft: '4px', borderLeft: '1px solid rgba(255,255,255,0.3)', paddingLeft: '6px' }}>
                            {Math.round((displaySignal?.confidence || 0) * 100)}%
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
                        {displayReasoning}
                    </div>
                )}
            </div>
        </div>
    );
};
