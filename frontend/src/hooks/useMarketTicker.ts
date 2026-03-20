import { useState, useEffect } from 'react';

export interface TickerData {
  symbol: string;
  price: number;
  change24h: number;
  bid: number;
  bid_qty: number;
  ask: number;
  ask_qty: number;
  timestamp: number;
  levels?: number;
  bids?: [number, number][];
  asks?: [number, number][];
  spread?: number;
  spread_pct?: number;
  bid_depth_qty?: number;
  ask_depth_qty?: number;
  bid_depth_notional?: number;
  ask_depth_notional?: number;
  depth_imbalance?: number;
  status?: string;
}

export const useMarketTicker = (symbol: string = 'BTC/USDT') => {
  const [ticker, setTicker] = useState<TickerData | null>(null);
  
  useEffect(() => {
    let isMounted = true;
    
    const fetchTicker = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const res = await fetch(`${apiBase}/api/v1/market/ticker?symbol=${encodeURIComponent(symbol)}&levels=8`);
        
        if (res.ok && isMounted) {
            const data = await res.json();
            if (data.price > 0) {
                setTicker(data);
            }
        }
      } catch (e) {
        // console.error("Ticker fetch error", e);
      }
    };

    fetchTicker();
    const interval = setInterval(fetchTicker, 1000); // 1s polling
    
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [symbol]);

  return ticker;
};
