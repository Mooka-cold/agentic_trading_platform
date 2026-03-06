"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, ArrowDownRight, Activity, ShieldCheck } from "lucide-react";

interface Position {
    symbol: string;
    side: string;
    size: number;
    entry_price: number;
    opened_at: string;
}

export const PortfolioCard = () => {
    const [positions, setPositions] = useState<Position[]>([]);
    
    // Poll positions every 3 seconds
    useEffect(() => {
        const fetchPositions = async () => {
            try {
                // Using direct localhost:8000 for MVP
                const res = await fetch("http://localhost:8000/api/v1/trade/positions");
                if (res.ok) {
                    setPositions(await res.json());
                }
            } catch (e) {
                console.error("Failed to fetch positions", e);
            }
        };
        
        fetchPositions();
        const interval = setInterval(fetchPositions, 3000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', backgroundColor: '#0f172a', borderRadius: '16px', border: '1px solid #1e293b', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h2 style={{ fontSize: '16px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px', color: 'white' }}>
                    <Activity size={18} className="text-blue-500" />
                    Live Portfolio
                </h2>
                <div className="flex items-center gap-1 text-xs text-green-500 font-mono bg-green-900/30 px-2 py-1 rounded">
                    <ShieldCheck size={12} />
                    <span>GUARDIAN ACTIVE</span>
                </div>
            </div>

            <div style={{ flex: 1, overflowY: 'auto' }}>
                {positions.length === 0 ? (
                    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#64748b', gap: '12px' }}>
                        <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justifyContent-center">
                            <Activity size={20} className="text-slate-600" />
                        </div>
                        <span style={{ fontSize: '13px' }}>No active positions</span>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {positions.map((pos, i) => (
                            <PositionRow key={i} pos={pos} />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

const PositionRow = ({ pos }: { pos: Position }) => {
    return (
        <div style={{ backgroundColor: '#1e293b', borderRadius: '8px', padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderLeft: `4px solid ${pos.side === 'LONG' ? '#4ade80' : '#f87171'}` }}>
            <div>
                <div style={{ fontWeight: 'bold', fontSize: '14px', color: 'white' }}>{pos.symbol}</div>
                <div style={{ fontSize: '11px', color: pos.side === 'LONG' ? '#4ade80' : '#f87171', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    {pos.side === 'LONG' ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                    {pos.side} {pos.size}
                </div>
            </div>
            <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8', textTransform: 'uppercase' }}>Entry Price</div>
                <div style={{ fontSize: '13px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                    ${pos.entry_price.toFixed(2)}
                </div>
            </div>
        </div>
    );
};
