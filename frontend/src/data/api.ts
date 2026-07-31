import { Session, SystemKPIs } from '@/types';

const API_BASE = '/api/v1';

export interface SystemConfigItem {
  key: string;
  value: string;
  description?: string | null;
  updated_at?: string;
}

export async function fetchPaperAccountSnapshot(): Promise<any> {
  const res = await authFetch(`/trade/paper/account`);
  return res.json();
}

export async function fetchPaperAccount(): Promise<SystemKPIs> {
  const data = await fetchPaperAccountSnapshot();
  
  return {
    totalPnl: data.equity - data.daily_start, // approximation for now
    dailyPnl: data.unrealized_pnl, // approximation
    maxDrawdown: -2.5, // placeholder
    winRate: 0.65, // placeholder
    currentLeverage: 1.0, // placeholder
    riskGateTriggeredCount: 0,
    totalSessions: 0,
    completedSessions: 0,
    rejectedSessions: 0,
    failedSessions: 0,
  };
}

export async function fetchSessions(): Promise<any[]> {
  const res = await authFetch(`/workflow/history?limit=50`);
  const data = await res.json();
  return data.history;
}

export async function fetchWorkflowRunnerStatus(): Promise<{ is_running: boolean; symbol?: string; session_id?: string; error?: string }> {
  const res = await authFetch(`/workflow/runner/status`);
  return res.json();
}

export async function runWorkflow(symbol: string, session_id?: string): Promise<any> {
  const res = await authFetch(`/workflow/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, session_id }),
  });
  return res.json();
}

export async function stopWorkflow(): Promise<any> {
  const res = await authFetch(`/workflow/stop`, { method: 'POST' });
  return res.json();
}

export async function fetchSessionDetail(sessionId: string): Promise<any> {
  const res = await authFetch(`/workflow/session/${sessionId}`);
  const data = await res.json();
  return data.session;
}

export async function fetchPositions(): Promise<any[]> {
  const res = await authFetch(`/trade/positions`);
  const data = await res.json();
  return data;
}

export async function fetchOrders(): Promise<any[]> {
  const res = await authFetch(`/trade/orders`);
  const data = await res.json();
  return data;
}

export async function fetchMarketKline(symbol: string, interval: string, limit = 120): Promise<any[]> {
  const params = new URLSearchParams({
    symbol,
    interval,
    limit: String(limit),
  });
  const res = await authFetch(`/market/kline?${params.toString()}`);
  return res.json();
}

export async function fetchMarketTicker(symbol: string, levels = 10): Promise<any> {
  const params = new URLSearchParams({
    symbol,
    levels: String(levels),
  });
  const res = await authFetch(`/market/ticker?${params.toString()}`);
  return res.json();
}

export async function fetchNews(limit = 20): Promise<any[]> {
  const res = await authFetch(`/news?limit=${limit}`);
  return res.json();
}

export async function fetchLatestSignal(symbol: string): Promise<any | null> {
  const res = await authFetch(`/signals/latest?symbol=${encodeURIComponent(symbol)}`);
  return res.json();
}



export async function fetchSentimentInterpretations(symbol: string, limit = 20, scope = 'all'): Promise<any[]> {
  const params = new URLSearchParams({
    symbol,
    limit: String(limit),
    scope,
  });
  const res = await authFetch(`/system/sentiment/interpretations?${params.toString()}`);
  return res.json();
}



export async function fetchSystemConfigs(): Promise<SystemConfigItem[]> {
  const res = await authFetch(`/system/config`);
  return res.json();
}

export async function upsertSystemConfig(
  key: string,
  value: string,
  description?: string,
): Promise<SystemConfigItem> {
  const res = await authFetch(`/system/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, value, description }),
  });
  return res.json();
}

export async function reloadSystemConfigs(): Promise<any> {
  const res = await authFetch(`/system/reload`, { method: 'POST' });
  return res.json();
}

export async function fetchSecondSeries(symbol: string, window = 600): Promise<{ symbol: string; window: number; points: any[] }> {
  const params = new URLSearchParams({
    symbol,
    window: String(window),
  });
  const res = await authFetch(`/market/seconds?${params.toString()}`);
  return res.json();
}

export async function solidifyMarketRollups(symbol: string, limitHint = 600): Promise<any> {
  const params = new URLSearchParams({
    symbols: symbol,
    limit_hint: String(limitHint),
  });
  const res = await authFetch(`/market/rollup/solidify?${params.toString()}`, {
    method: 'POST',
  });
  return res.json();
}

// ----------------- JWT & Auth Interceptor -----------------

// Helper to get token
export function getToken() {
  return localStorage.getItem('access_token');
}

// Custom wrapper for generic API calls needing auth
async function authFetch(endpoint: string, options: RequestInit = {}) {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  });
  
  if (response.status === 401) {
    // Handle unauthorized - optionally redirect to login
    // window.location.href = '/login';
    localStorage.removeItem('access_token');
    throw new Error('Unauthorized');
  }
  
  return response;
}

export const api = {
  get: async (url: string) => {
    // Strip API_BASE if it's already there to prevent duplication
    const cleanUrl = url.startsWith(API_BASE) ? url.slice(API_BASE.length) : url;
    const res = await authFetch(cleanUrl);
    if (!res.ok) throw new Error(`GET ${url} failed`);
    return { data: await res.json() };
  },
  post: async (url: string, data: any) => {
    const cleanUrl = url.startsWith(API_BASE) ? url.slice(API_BASE.length) : url;
    const res = await authFetch(cleanUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`POST ${url} failed`);
    return { data: await res.json() };
  },
  put: async (url: string, data: any) => {
    const cleanUrl = url.startsWith(API_BASE) ? url.slice(API_BASE.length) : url;
    const res = await authFetch(cleanUrl, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`PUT ${url} failed`);
    return { data: await res.json() };
  }
};
