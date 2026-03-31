import { useEffect, useMemo, useState } from 'react';
import { Panel, MetricCard, StatusBadge } from '@/components/shared/StatusBadge';
import { fetchLatestSignal, fetchMarketKline, fetchMarketTicker, fetchNews } from '@/data/api';
import { Activity, Newspaper, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { cn } from '@/lib/utils';

type KlineItem = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  rsi?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  atr_14?: number | null;
  sma_7?: number | null;
  sma_25?: number | null;
  ema_7?: number | null;
  ema_25?: number | null;
  bb_upper?: number | null;
  bb_middle?: number | null;
  bb_lower?: number | null;
};

type TickerItem = {
  symbol: string;
  price: number;
  change24h: number;
  bid: number;
  ask: number;
  spread: number;
  spread_pct: number;
  depth_imbalance: number;
  bids: [number, number][];
  asks: [number, number][];
  status?: string;
};

type NewsItem = {
  id: string;
  title: string;
  summary: string;
  source: string;
  sentiment: string | null;
  published_at: string;
  url: string;
};

type SignalItem = {
  action: string;
  confidence: number;
  reasoning: string;
  model_used: string;
  created_at: string;
} | null;

const SYMBOL_OPTIONS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'];
const INTERVAL_OPTIONS = ['1m', '5m', '15m', '1h', '4h', '1d'];

export default function DashboardPage() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [interval, setInterval] = useState('1m');
  const [loading, setLoading] = useState(false);
  const [kline, setKline] = useState<KlineItem[]>([]);
  const [ticker, setTicker] = useState<TickerItem | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [signal, setSignal] = useState<SignalItem>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [klineData, tickerData, newsData, signalData] = await Promise.all([
        fetchMarketKline(symbol, interval, 120),
        fetchMarketTicker(symbol, 10),
        fetchNews(20),
        fetchLatestSignal(symbol),
      ]);
      setKline(klineData || []);
      setTicker(tickerData || null);
      setNews(newsData || []);
      setSignal(signalData || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, [symbol, interval]);

  useEffect(() => {
    const timer = setInterval(() => {
      fetchMarketTicker(symbol, 10).then(setTicker).catch(() => null);
    }, 5000);
    return () => clearInterval(timer);
  }, [symbol]);

  const latest = kline[kline.length - 1];
  const chartData = useMemo(
    () =>
      kline.map((item) => ({
        ...item,
        t: new Date(item.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      })),
    [kline],
  );

  return (
    <div className="space-y-6 animate-slide-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-mono font-bold text-foreground">Market Dashboard</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">K线、因子、Ticker、Order Book、新闻与LLM解读</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          >
            {SYMBOL_OPTIONS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <select
            value={interval}
            onChange={(e) => setInterval(e.target.value)}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          >
            {INTERVAL_OPTIONS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
            刷新
          </Button>
        </div>
      </div>

      {error && <div className="rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
        <MetricCard label="Price" value={ticker?.price ? `$${ticker.price.toLocaleString()}` : '—'} />
        <MetricCard label="24H Change" value={ticker ? `${ticker.change24h.toFixed(2)}%` : '—'} trend={(ticker?.change24h || 0) >= 0 ? 'up' : 'down'} />
        <MetricCard label="RSI(14)" value={latest?.rsi?.toFixed(2) ?? '—'} />
        <MetricCard label="MACD" value={latest?.macd?.toFixed(4) ?? '—'} />
        <MetricCard label="ATR(14)" value={latest?.atr_14?.toFixed(4) ?? '—'} />
        <MetricCard label="Spread" value={ticker ? `${ticker.spread.toFixed(4)}` : '—'} />
        <MetricCard label="Spread %" value={ticker ? `${ticker.spread_pct.toFixed(3)}%` : '—'} />
        <MetricCard label="Imbalance" value={ticker ? ticker.depth_imbalance.toFixed(3) : '—'} trend={(ticker?.depth_imbalance || 0) >= 0 ? 'up' : 'down'} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Panel title="K线与技术指标" className="xl:col-span-2">
          <div className="h-[420px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="t" tick={{ fontSize: 11 }} minTickGap={18} />
                <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} width={70} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
                  labelStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Line type="monotone" dataKey="close" stroke="#3b82f6" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="sma_7" stroke="#22c55e" dot={false} strokeWidth={1.5} />
                <Line type="monotone" dataKey="sma_25" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                <Line type="monotone" dataKey="bb_upper" stroke="#a855f7" dot={false} strokeWidth={1} />
                <Line type="monotone" dataKey="bb_lower" stroke="#a855f7" dot={false} strokeWidth={1} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Ticker / Order Book">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Feed Status</span>
              <StatusBadge status={ticker?.status === 'connecting' ? 'degraded' : 'fresh'} />
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div className="rounded border border-border p-2">
                <p className="text-muted-foreground">Bid</p>
                <p className="text-success text-sm">{ticker?.bid?.toLocaleString() ?? '—'}</p>
              </div>
              <div className="rounded border border-border p-2">
                <p className="text-muted-foreground">Ask</p>
                <p className="text-danger text-sm">{ticker?.ask?.toLocaleString() ?? '—'}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-success font-semibold mb-1">Bids</p>
                <div className="space-y-1">
                  {(ticker?.bids || []).slice(0, 8).map(([p, q], idx) => (
                    <div key={`b-${idx}`} className="flex justify-between text-[11px] font-mono">
                      <span className="text-success">{p.toFixed(2)}</span>
                      <span className="text-muted-foreground">{q.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-danger font-semibold mb-1">Asks</p>
                <div className="space-y-1">
                  {(ticker?.asks || []).slice(0, 8).map(([p, q], idx) => (
                    <div key={`a-${idx}`} className="flex justify-between text-[11px] font-mono">
                      <span className="text-danger">{p.toFixed(2)}</span>
                      <span className="text-muted-foreground">{q.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Latest News" actions={<Newspaper className="h-4 w-4 text-muted-foreground" />}>
          <div className="space-y-3 max-h-[360px] overflow-auto">
            {news.slice(0, 12).map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="block rounded-md border border-border p-3 hover:bg-secondary/30 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-foreground line-clamp-2">{item.title}</p>
                  <StatusBadge status={item.sentiment === 'negative' ? 'critical' : item.sentiment === 'positive' ? 'info' : 'warning'} />
                </div>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{item.summary || '无摘要'}</p>
                <p className="text-[11px] text-muted-foreground mt-2">
                  {item.source} · {new Date(item.published_at).toLocaleString()}
                </p>
              </a>
            ))}
            {!news.length && <div className="text-sm text-muted-foreground">暂无新闻数据</div>}
          </div>
        </Panel>

        <Panel title="LLM 解读（最新信号）" actions={<Activity className="h-4 w-4 text-muted-foreground" />}>
          {!signal ? (
            <div className="text-sm text-muted-foreground">暂无LLM解读结果</div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <StatusBadge status={signal.action === 'BUY' ? 'ACCEPTED' : signal.action === 'SELL' ? 'REJECTED' : 'PENDING'} />
                <span className="text-xs text-muted-foreground">
                  model: {signal.model_used} · {new Date(signal.created_at).toLocaleString()}
                </span>
              </div>
              <div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{signal.reasoning}</div>
              <div className="text-xs text-muted-foreground">
                confidence: {(signal.confidence * 100).toFixed(1)}%
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
