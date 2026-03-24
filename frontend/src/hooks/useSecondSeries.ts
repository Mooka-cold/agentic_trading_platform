import { useEffect, useState } from 'react';
import { API_BASE_URL } from '@/lib/api/base';

export interface SecondPoint {
  time: number;
  price: number;
  bid: number | null;
  ask: number | null;
}

export const useSecondSeries = (symbol: string = 'BTC/USDT', window: number = 600) => {
  const [points, setPoints] = useState<SecondPoint[]>([]);

  useEffect(() => {
    let isMounted = true;

    const fetchSeries = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/market/seconds?symbol=${encodeURIComponent(symbol)}&window=${window}`);
        if (!res.ok || !isMounted) return;
        const data = await res.json();
        if (Array.isArray(data?.points)) {
          setPoints(data.points);
        }
      } catch (e) {
        void e;
      }
    };

    fetchSeries();
    const interval = setInterval(fetchSeries, 1000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [symbol, window]);

  return points;
};
