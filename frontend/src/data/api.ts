import { Session, SystemKPIs } from '@/types';

const API_BASE = '/api/v1';

export async function fetchPaperAccountSnapshot(): Promise<any> {
  const res = await fetch(`${API_BASE}/trade/paper/account`);
  if (!res.ok) throw new Error('Failed to fetch account snapshot');
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
  const res = await fetch(`${API_BASE}/workflow/history?limit=50`);
  if (!res.ok) throw new Error('Failed to fetch sessions');
  const data = await res.json();
  return data.history;
}

export async function fetchWorkflowRunnerStatus(): Promise<{ is_running: boolean; symbol?: string; session_id?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/workflow/runner/status`);
  if (!res.ok) throw new Error('Failed to fetch workflow runner status');
  return res.json();
}

export async function runWorkflow(symbol: string, session_id?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/workflow/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, session_id }),
  });
  if (!res.ok) throw new Error('Failed to run workflow');
  return res.json();
}

export async function stopWorkflow(): Promise<any> {
  const res = await fetch(`${API_BASE}/workflow/stop`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop workflow');
  return res.json();
}

export async function fetchSessionDetail(sessionId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/workflow/session/${sessionId}`);
  if (!res.ok) throw new Error('Failed to fetch session detail');
  const data = await res.json();
  return data.session;
}

export async function fetchPositions(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/trade/positions`);
  if (!res.ok) throw new Error('Failed to fetch positions');
  const data = await res.json();
  return data;
}

export async function fetchOrders(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/trade/orders`);
  if (!res.ok) throw new Error('Failed to fetch orders');
  const data = await res.json();
  return data;
}

export async function fetchMarketKline(symbol: string, interval: string, limit = 120): Promise<any[]> {
  const params = new URLSearchParams({
    symbol,
    interval,
    limit: String(limit),
  });
  const res = await fetch(`${API_BASE}/market/kline?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch kline');
  return res.json();
}

export async function fetchMarketTicker(symbol: string, levels = 10): Promise<any> {
  const params = new URLSearchParams({
    symbol,
    levels: String(levels),
  });
  const res = await fetch(`${API_BASE}/market/ticker?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch ticker');
  return res.json();
}

export async function fetchNews(limit = 20): Promise<any[]> {
  const res = await fetch(`${API_BASE}/news?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch news');
  return res.json();
}

export async function fetchLatestSignal(symbol: string): Promise<any | null> {
  const res = await fetch(`${API_BASE}/signals/latest?symbol=${encodeURIComponent(symbol)}`);
  if (!res.ok) throw new Error('Failed to fetch latest signal');
  return res.json();
}

export async function fetchSentimentAggregate(symbol: string): Promise<any | null> {
  const res = await fetch(`${API_BASE}/system/sentiment/aggregate?symbol=${encodeURIComponent(symbol)}`);
  if (!res.ok) throw new Error('Failed to fetch sentiment aggregate');
  return res.json();
}

export async function fetchSentimentInterpretations(symbol: string, limit = 20, scope = 'all'): Promise<any[]> {
  const params = new URLSearchParams({
    symbol,
    limit: String(limit),
    scope,
  });
  const res = await fetch(`${API_BASE}/system/sentiment/interpretations?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch sentiment interpretations');
  return res.json();
}

export async function fetchSentimentDashboard(symbol: string): Promise<any> {
  const res = await fetch(`${API_BASE}/system/sentiment/dashboard?symbol=${encodeURIComponent(symbol)}`);
  if (!res.ok) throw new Error('Failed to fetch sentiment dashboard');
  return res.json();
}

export async function fetchSecondSeries(symbol: string, window = 600): Promise<{ symbol: string; window: number; points: any[] }> {
  const params = new URLSearchParams({
    symbol,
    window: String(window),
  });
  const res = await fetch(`${API_BASE}/market/seconds?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch second series');
  return res.json();
}
