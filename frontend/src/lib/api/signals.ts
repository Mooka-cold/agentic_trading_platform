const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Signal {
  id: string;
  symbol: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  reasoning: string;
  model_used: string;
  created_at: string;
}

export const SignalsAPI = {
  getLatest: async (symbol: string): Promise<Signal | null> => {
    try {
      const res = await fetch(`${API_URL}/api/v1/signals/latest?symbol=${encodeURIComponent(symbol)}`);
      if (!res.ok) {
        if (res.status === 404) return null;
        console.error('API Error:', res.statusText);
        return null;
      }
      return await res.json();
    } catch (error) {
      console.error('Fetch Error:', error);
      return null;
    }
  },

  getHistory: async (symbol?: string, limit: number = 20): Promise<Signal[]> => {
    try {
      let url = `${API_URL}/api/v1/signals/?limit=${limit}`;
      if (symbol) {
        url += `&symbol=${encodeURIComponent(symbol)}`;
      }
      
      const res = await fetch(url);
      if (!res.ok) {
        console.error('API Error:', res.statusText);
        return [];
      }
      return await res.json();
    } catch (error) {
      console.error('Fetch Error:', error);
      return [];
    }
  }
};
