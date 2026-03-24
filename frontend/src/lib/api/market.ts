import { API_BASE_URL } from "./base";

export interface KlineData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  rsi?: number;
  macd?: number;
  macd_signal?: number;
  macd_hist?: number;
  ma20?: number;
  ma50?: number;
  sma_7?: number;
  sma_25?: number;
  ema_7?: number;
  ema_25?: number;
  bb_upper?: number;
  bb_middle?: number;
  bb_lower?: number;
  atr_14?: number;
  rsi_calc_time?: number | null;
  macd_calc_time?: number | null;
  macd_signal_calc_time?: number | null;
  macd_hist_calc_time?: number | null;
  ma20_calc_time?: number | null;
  ma50_calc_time?: number | null;
  sma_7_calc_time?: number | null;
  sma_25_calc_time?: number | null;
  ema_7_calc_time?: number | null;
  ema_25_calc_time?: number | null;
  bb_upper_calc_time?: number | null;
  bb_middle_calc_time?: number | null;
  bb_lower_calc_time?: number | null;
  atr_14_calc_time?: number | null;
}

export const MarketAPI = {
  getKline: async (symbol: string, interval: string = '1m', limit: number = 100): Promise<KlineData[]> => {
    try {
      // Use encodeURIComponent for symbol (e.g., BTC/USDT -> BTC%2FUSDT)
      const res = await fetch(`${API_BASE_URL}/api/v1/market/kline?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`);
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
