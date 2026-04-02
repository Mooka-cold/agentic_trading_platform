import { useEffect, useMemo, useState } from 'react';
import { Panel, MetricCard, StatusBadge } from '@/components/shared/StatusBadge';
import { fetchMarketKline, fetchMarketTicker, fetchNews, fetchSecondSeries, fetchSentimentDashboard, fetchSentimentInterpretations } from '@/data/api';
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

type SecondSeriesPoint = {
  time: number;
  price: number;
};

type NewsInterpretationItem = {
  news_id: string;
  summary_cn: string;
  confidence: number;
  bias: string;
  severity: string;
  final_status: string;
  language: string;
  source_tier: string;
  evidence_quotes: string[];
  noise_flags: string[];
  cross_market_impacts: Array<{
    market: string;
    direction: string;
    magnitude: number;
    confidence: number;
    horizon: string;
    reason: string;
  }>;
};

type SentimentWindowScore = {
  market: string;
  label: string;
  score: number;
  bias: string;
  sample_count: number;
};

type SentimentWindowSummary = {
  label: string;
  start_at: string;
  end_at: string;
  scores: SentimentWindowScore[];
};

type SentimentDashboardData = {
  markets: Array<{ key: string; label: string }>;
  current_hour: SentimentWindowSummary;
  rolling_6h: SentimentWindowSummary;
  rolling_24h: SentimentWindowSummary;
  chart: Array<{
    bucket_start: string;
    bucket_end: string;
    label: string;
    markets: Record<string, { hourly: number; rolling6h: number; rolling24h: number }>;
  }>;
} | null;

type ChartMode = 'kline' | 'seconds' | 'overlay';
const MARKET_LABELS: Record<string, string> = {
  CRYPTO: '加密资产',
  US_EQUITY: '美股',
  FX: '外汇',
  RATES: '利率',
  COMMODITY: '商品',
};

const SYMBOL_OPTIONS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'];
const INTERVAL_OPTIONS = ['1m', '1h', '1d'];

export default function DashboardPage() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [interval, setInterval] = useState('1m');
  const [loading, setLoading] = useState(false);
  const [kline, setKline] = useState<KlineItem[]>([]);
  const [secondSeries, setSecondSeries] = useState<SecondSeriesPoint[]>([]);
  const [ticker, setTicker] = useState<TickerItem | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [interpretations, setInterpretations] = useState<NewsInterpretationItem[]>([]);
  const [sentimentDashboard, setSentimentDashboard] = useState<SentimentDashboardData>(null);
  const [error, setError] = useState<string | null>(null);
  const [usingSecondFallback, setUsingSecondFallback] = useState(false);
  const [chartMode, setChartMode] = useState<ChartMode>('kline');
  const [selectedSentimentMarket, setSelectedSentimentMarket] = useState('CRYPTO');

  const refresh = async () => {
    setLoading(true);
    setError(null);
    setUsingSecondFallback(false);
    const [klineResult, tickerResult, newsResult, interpretationsResult, sentimentDashboardResult] = await Promise.allSettled([
      fetchMarketKline(symbol, interval, 120),
      fetchMarketTicker(symbol, 10),
      fetchNews(20),
      fetchSentimentInterpretations(symbol, 40, 'all'),
      fetchSentimentDashboard(symbol),
    ]);

    const failedModules: string[] = [];

    if (klineResult.status === 'fulfilled' && (klineResult.value || []).length > 0) {
      setKline(klineResult.value || []);
    } else {
      setKline([]);
      failedModules.push('K线');
    }

    if (tickerResult.status === 'fulfilled') {
      setTicker(tickerResult.value || null);
    } else {
      setTicker(null);
      failedModules.push('Ticker/OrderBook');
    }

    if (newsResult.status === 'fulfilled') {
      setNews(newsResult.value || []);
    } else {
      setNews([]);
      failedModules.push('新闻');
    }

    if (interpretationsResult.status === 'fulfilled') {
      setInterpretations(interpretationsResult.value || []);
    } else {
      setInterpretations([]);
      failedModules.push('LLM解读');
    }

    if (sentimentDashboardResult.status === 'fulfilled') {
      setSentimentDashboard(sentimentDashboardResult.value || null);
    } else {
      setSentimentDashboard(null);
      if (!failedModules.includes('LLM解读')) failedModules.push('LLM解读');
    }

    let secondSeriesPoints: SecondSeriesPoint[] = [];
    try {
      const secondSeriesResult = await fetchSecondSeries(symbol, 600);
      const points = (secondSeriesResult?.points || []).map((p) => ({
        time: Number(p.time),
        price: Number(p.price || 0),
      }));
      secondSeriesPoints = points;
      setSecondSeries(points);
    } catch {
      setSecondSeries([]);
    }

    if (failedModules.length) {
      setError(`部分数据加载失败：${failedModules.join('、')}`);
    }

    if (klineResult.status !== 'fulfilled' || (klineResult.value || []).length === 0) {
      try {
        const points = secondSeriesPoints.length
          ? secondSeriesPoints
          : (await fetchSecondSeries(symbol, 600))?.points?.map((p: any) => ({
              time: Number(p.time),
              price: Number(p.price || 0),
            })) || [];
        if (points.length) {
          const fallbackKline: KlineItem[] = points.map((p) => {
            const price = Number(p.price || 0);
            return {
              time: Number(p.time),
              open: price,
              high: price,
              low: price,
              close: price,
              volume: 0,
            };
          });
          setKline(fallbackKline);
          setUsingSecondFallback(true);
          setError('K线历史数据暂缺，已回退为秒级价格曲线');
        }
      } catch {}
    }

    setLoading(false);
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
  const secondSeriesChartData = useMemo(
    () =>
      secondSeries.map((item) => ({
        ...item,
        t: new Date(item.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      })),
    [secondSeries],
  );
  const interpretationMap = useMemo(() => {
    const map = new Map<string, NewsInterpretationItem>();
    for (const item of interpretations) {
      map.set(String(item.news_id), item);
    }
    return map;
  }, [interpretations]);
  const overlayChartData = useMemo(() => {
    const merged = new Map<number, { time: number; close?: number; secondPrice?: number; sma_7?: number | null; sma_25?: number | null }>();
    for (const item of kline) {
      merged.set(item.time, {
        ...(merged.get(item.time) || { time: item.time }),
        time: item.time,
        close: item.close,
        sma_7: item.sma_7,
        sma_25: item.sma_25,
      });
    }
    for (const item of secondSeries) {
      merged.set(item.time, {
        ...(merged.get(item.time) || { time: item.time }),
        time: item.time,
        secondPrice: item.price,
      });
    }
    return Array.from(merged.values())
      .sort((a, b) => a.time - b.time)
      .map((item) => ({
        ...item,
        t: new Date(item.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      }));
  }, [kline, secondSeries]);
  const sentimentChartData = useMemo(
    () =>
      (sentimentDashboard?.chart || []).map((point) => ({
        label: point.label,
        hourly: point.markets?.[selectedSentimentMarket]?.hourly ?? 0,
        rolling6h: point.markets?.[selectedSentimentMarket]?.rolling6h ?? 0,
        rolling24h: point.markets?.[selectedSentimentMarket]?.rolling24h ?? 0,
      })),
    [selectedSentimentMarket, sentimentDashboard],
  );

  useEffect(() => {
    const available = sentimentDashboard?.markets || [];
    if (!available.length) return;
    if (!available.some((item) => item.key === selectedSentimentMarket)) {
      setSelectedSentimentMarket(available[0].key);
    }
  }, [selectedSentimentMarket, sentimentDashboard]);

  const latestNewsRows = useMemo(
    () =>
      news.slice(0, 12).map((item) => ({
        news: item,
        interpretation: interpretationMap.get(String(item.id)),
      })),
    [interpretationMap, news],
  );

  const scoreColorClass = (score: number) => {
    if (score >= 1.5) return 'text-success';
    if (score <= -1.5) return 'text-danger';
    return 'text-muted-foreground';
  };

  const formatScore = (score: number) => `${score > 0 ? '+' : ''}${score.toFixed(1)}`;
  const finalStatusLabel = (status?: string) => {
    if (status === 'verified') return '已验证';
    if (status === 'partially_verified') return '部分验证';
    if (status === 'insufficient_evidence') return '证据不足';
    return '状态未知';
  };
  const finalStatusClass = (status?: string) => {
    if (status === 'verified') return 'border-success/30 bg-success/10 text-success';
    if (status === 'partially_verified') return 'border-warning/30 bg-warning/10 text-warning';
    if (status === 'insufficient_evidence') return 'border-danger/30 bg-danger/10 text-danger';
    return 'border-border bg-secondary/20 text-muted-foreground';
  };
  const severityLabel = (severity?: string) => {
    if (severity === 'critical') return '严重';
    if (severity === 'high') return '高';
    if (severity === 'medium') return '中';
    if (severity === 'low') return '低';
    return '未知';
  };
  const severityClass = (severity?: string) => {
    if (severity === 'critical') return 'border-danger/30 bg-danger/10 text-danger';
    if (severity === 'high') return 'border-warning/30 bg-warning/10 text-warning';
    if (severity === 'medium') return 'border-primary/30 bg-primary/10 text-primary';
    return 'border-border bg-secondary/20 text-muted-foreground';
  };
  const noiseFlagLabel = (flag: string) => {
    if (flag === 'anonymous_source') return '匿名来源';
    if (flag === 'no_primary_evidence') return '无一手证据';
    if (flag === 'emotional_wording') return '情绪化措辞';
    if (flag === 'secondary_repost') return '二次转述';
    if (flag === 'time_ambiguity') return '时间模糊';
    return flag;
  };
  const languageLabel = (language?: string) => {
    if (language === 'zh') return '中文';
    if (language === 'en') return '英文';
    return language || '未知语言';
  };
  const sourceTierLabel = (tier?: string) => {
    if (tier === 'top_tier') return 'Top Tier';
    if (tier === 'mainstream') return 'Mainstream';
    if (tier === 'secondary') return 'Secondary';
    return tier || '未知来源层级';
  };

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
        <MetricCard label="24H Change" value={typeof ticker?.change24h === 'number' ? `${ticker.change24h.toFixed(2)}%` : '—'} trend={(ticker?.change24h || 0) >= 0 ? 'up' : 'down'} />
        <MetricCard label="RSI(14)" value={latest?.rsi?.toFixed(2) ?? '—'} />
        <MetricCard label="MACD" value={latest?.macd?.toFixed(4) ?? '—'} />
        <MetricCard label="ATR(14)" value={latest?.atr_14?.toFixed(4) ?? '—'} />
        <MetricCard label="Spread" value={typeof ticker?.spread === 'number' ? `${ticker.spread.toFixed(4)}` : '—'} />
        <MetricCard label="Spread %" value={typeof ticker?.spread_pct === 'number' ? `${ticker.spread_pct.toFixed(3)}%` : '—'} />
        <MetricCard label="Imbalance" value={typeof ticker?.depth_imbalance === 'number' ? ticker.depth_imbalance.toFixed(3) : '—'} trend={(ticker?.depth_imbalance || 0) >= 0 ? 'up' : 'down'} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Panel
          title="K线与技术指标"
          className="xl:col-span-2"
          actions={
            <div className="flex items-center gap-2">
              {usingSecondFallback && <span className="text-[11px] text-amber-400">当前使用秒级数据回退</span>}
              {(['kline', 'seconds', 'overlay'] as ChartMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setChartMode(mode)}
                  className={cn(
                    'rounded border px-2 py-1 text-[11px] font-mono transition-colors',
                    chartMode === mode ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground',
                  )}
                >
                  {mode === 'kline' ? 'K线' : mode === 'seconds' ? '秒级' : '叠加'}
                </button>
              ))}
            </div>
          }
        >
          <div className="h-[420px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartMode === 'kline' ? chartData : chartMode === 'seconds' ? secondSeriesChartData : overlayChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="t" tick={{ fontSize: 11 }} minTickGap={18} />
                <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} width={70} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
                  labelStyle={{ color: 'hsl(var(--foreground))' }}
                />
                {chartMode !== 'seconds' && <Line type="monotone" dataKey="close" stroke="#3b82f6" dot={false} strokeWidth={2} />}
                {chartMode === 'kline' && <Line type="monotone" dataKey="sma_7" stroke="#22c55e" dot={false} strokeWidth={1.5} />}
                {chartMode === 'kline' && <Line type="monotone" dataKey="sma_25" stroke="#f59e0b" dot={false} strokeWidth={1.5} />}
                {chartMode === 'kline' && <Line type="monotone" dataKey="bb_upper" stroke="#a855f7" dot={false} strokeWidth={1} />}
                {chartMode === 'kline' && <Line type="monotone" dataKey="bb_lower" stroke="#a855f7" dot={false} strokeWidth={1} />}
                {chartMode === 'seconds' && <Line type="monotone" dataKey="price" stroke="#38bdf8" dot={false} strokeWidth={2} />}
                {chartMode === 'overlay' && <Line type="monotone" dataKey="secondPrice" stroke="#38bdf8" dot={false} strokeWidth={2} />}
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

      <Panel title="秒级价格曲线">
        <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
          <span>数据窗口：最近 600 秒</span>
          <span>{secondSeriesChartData.length ? '来自 /market/seconds' : '暂无秒级数据'}</span>
        </div>
        <div className="h-[260px]">
          {secondSeriesChartData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={secondSeriesChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="t" tick={{ fontSize: 11 }} minTickGap={24} />
                <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} width={70} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
                  labelStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Line type="monotone" dataKey="price" stroke="#38bdf8" dot={false} strokeWidth={2} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              暂无秒级价格数据
            </div>
          )}
        </div>
      </Panel>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Latest News" actions={<Newspaper className="h-4 w-4 text-muted-foreground" />}>
          <div className="space-y-2 max-h-[520px] overflow-auto">
            {latestNewsRows.map(({ news: item, interpretation }) => (
              <div key={item.id} className="grid gap-0 rounded-md border border-border md:grid-cols-2">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block space-y-2 p-3 transition-colors hover:bg-secondary/20"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-foreground line-clamp-2">{item.title}</p>
                    <StatusBadge status={item.sentiment === 'negative' ? 'critical' : item.sentiment === 'positive' ? 'info' : 'warning'} />
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">{item.summary || '无摘要'}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {item.source} · {new Date(item.published_at).toLocaleString()}
                  </p>
                </a>
                <div className="space-y-2 border-t border-border p-3 md:border-l md:border-t-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">LLM Summary</p>
                    <div className="flex items-center gap-2">
                      {interpretation && (
                        <span className={cn('rounded border px-2 py-0.5 text-[10px] font-mono', severityClass(interpretation.severity))}>
                          {severityLabel(interpretation.severity)}
                        </span>
                      )}
                      {interpretation && (
                        <span className={cn('rounded border px-2 py-0.5 text-[10px] font-mono', finalStatusClass(interpretation.final_status))}>
                          {finalStatusLabel(interpretation.final_status)}
                        </span>
                      )}
                      <span className="text-[11px] text-muted-foreground">
                        {interpretation ? `${(interpretation.confidence * 100).toFixed(0)}%` : '待解读'}
                      </span>
                    </div>
                  </div>
                  <p className="text-sm text-foreground leading-relaxed">
                    {interpretation?.summary_cn || '这条新闻尚未完成逐条解读。'}
                  </p>
                  <div className="space-y-1">
                    <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Source Context</p>
                    <div className="flex flex-wrap gap-1.5">
                      <span className="rounded border border-border bg-secondary/20 px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
                        {interpretation ? languageLabel(interpretation.language) : '待识别语言'}
                      </span>
                      <span className="rounded border border-border bg-secondary/20 px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
                        {interpretation ? sourceTierLabel(interpretation.source_tier) : '待识别来源层级'}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(interpretation?.cross_market_impacts || []).slice(0, 3).map((impact, idx) => (
                      <span
                        key={`${impact.market}-${idx}`}
                        className={cn(
                          'rounded border px-2 py-0.5 text-[10px] font-mono',
                          impact.direction === 'bullish'
                            ? 'border-success/30 bg-success/10 text-success'
                            : impact.direction === 'bearish'
                              ? 'border-danger/30 bg-danger/10 text-danger'
                              : 'border-border bg-secondary/20 text-muted-foreground',
                        )}
                      >
                        {MARKET_LABELS[impact.market] || impact.market} {impact.direction === 'bullish' ? '利好' : impact.direction === 'bearish' ? '利空' : '中性'}
                      </span>
                    ))}
                    {!(interpretation?.cross_market_impacts || []).length && (
                      <span className="rounded border border-border bg-secondary/20 px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
                        暂无跨市场归因
                      </span>
                    )}
                  </div>
                  <div className="space-y-1">
                    <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Evidence</p>
                    {(interpretation?.evidence_quotes || []).slice(0, 2).map((quote, idx) => (
                      <p key={idx} className="rounded border border-border bg-secondary/10 px-2 py-1 text-xs text-muted-foreground line-clamp-2">
                        “{quote}”
                      </p>
                    ))}
                    {!(interpretation?.evidence_quotes || []).length && (
                      <p className="text-xs text-muted-foreground">暂无证据引用</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Noise Flags</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(interpretation?.noise_flags || []).slice(0, 3).map((flag) => (
                        <span key={flag} className="rounded border border-border bg-secondary/20 px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
                          {noiseFlagLabel(flag)}
                        </span>
                      ))}
                      {!(interpretation?.noise_flags || []).length && (
                        <span className="text-xs text-muted-foreground">无明显噪声标记</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {!latestNewsRows.length && <div className="text-sm text-muted-foreground">暂无新闻数据</div>}
          </div>
        </Panel>

        <Panel title="LLM 解读" actions={<Activity className="h-4 w-4 text-muted-foreground" />}>
          {sentimentDashboard ? (
            <div className="space-y-3">
              {[
                ['最近 1 个自然小时', sentimentDashboard.current_hour],
                ['最近 6 个自然小时', sentimentDashboard.rolling_6h],
                ['最近 24 个自然小时', sentimentDashboard.rolling_24h],
              ].map(([title, window]) => (
                <div key={title} className="rounded-md border border-border p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{title}</span>
                    <span className="text-[11px] text-muted-foreground">{window.label}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                    {window.scores.map((score) => (
                      <div key={score.market} className="rounded border border-border bg-secondary/10 p-2">
                        <div className="text-[11px] text-muted-foreground">{score.label}</div>
                        <div className={cn('mt-1 text-lg font-mono font-bold', scoreColorClass(score.score))}>
                          {formatScore(score.score)}
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                          {score.score > 1.5 ? '偏多' : score.score < -1.5 ? '偏空' : '中性'} · {score.sample_count} 条
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              <div className="rounded-md border border-border p-3">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                    情绪曲线 · {MARKET_LABELS[selectedSentimentMarket] || selectedSentimentMarket}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(sentimentDashboard.markets || []).map((market) => (
                      <button
                        key={market.key}
                        onClick={() => setSelectedSentimentMarket(market.key)}
                        className={cn(
                          'rounded border px-2 py-1 text-[11px] font-mono transition-colors',
                          selectedSentimentMarket === market.key
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border text-muted-foreground hover:text-foreground',
                        )}
                      >
                        {market.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="h-[240px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={sentimentChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={16} />
                      <YAxis domain={[-10, 10]} tick={{ fontSize: 11 }} width={48} />
                      <Tooltip
                        contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                      />
                      <Line type="monotone" dataKey="hourly" name="1H" stroke="#38bdf8" dot={false} strokeWidth={2} />
                      <Line type="monotone" dataKey="rolling6h" name="6H" stroke="#22c55e" dot={false} strokeWidth={2} />
                      <Line type="monotone" dataKey="rolling24h" name="24H" stroke="#f59e0b" dot={false} strokeWidth={2} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">暂无LLM解读结果</div>
          )}
        </Panel>
      </div>
    </div>
  );
}
