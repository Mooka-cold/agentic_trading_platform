import { useState, useEffect } from 'react';
import { MarketAPI, KlineData } from '@/lib/api/market';

export const useKlines = (symbol: string = 'BTC/USDT', timeframe: string = '1h') => {
  const [data, setData] = useState<KlineData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchKlines = async () => {
      try {
        setLoading(true);
        const result = await MarketAPI.getKline(symbol, timeframe, 200);
        
        if (isMounted) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchKlines();
    
    // Poll every 5 seconds
    const interval = setInterval(fetchKlines, 5000);
    
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [symbol, timeframe]);

  return { data, loading, error };
};
