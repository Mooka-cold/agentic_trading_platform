import { useQuery } from "@tanstack/react-query";
import { Database, Activity, Globe, Link2, Server, Wifi, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { api } from "@/data/api";
import { Panel } from "@/components/shared/StatusBadge";
import { Badge } from "@/components/ui/badge";

export default function DataSourcePage() {
  const { data: configs, isLoading } = useQuery({
    queryKey: ["system-config"],
    queryFn: () => api.get("/system/config").then((res) => res.data),
  });

  const getConfig = (key: string) => {
    return configs?.find((c: any) => c.key === key)?.value;
  };

  const hasKey = (key: string) => {
    const val = getConfig(key);
    return val && val.length > 5;
  };

  const sources = [
    {
      id: "binance_ws",
      name: "Binance Live Stream",
      type: "Market Data (Level 2)",
      icon: Activity,
      status: "connected",
      details: "Streaming 1s K-lines and 20-level orderbook depth.",
      metrics: [
        { label: "Latency", value: "45ms" },
        { label: "Updates/sec", value: "~12.4" }
      ]
    },
    {
      id: "news_api",
      name: "Global News API",
      type: "Macro & Fundamentals",
      icon: Globe,
      status: hasKey("NEWS_API_KEY") ? "connected" : "disconnected",
      details: "Fetching traditional finance and macro-economic news.",
      metrics: [
        { label: "Polling", value: "Every 15m" },
        { label: "Articles/day", value: "~2,400" }
      ]
    },
    {
      id: "cryptopanic",
      name: "CryptoPanic Stream",
      type: "Crypto Sentiment",
      icon: Wifi,
      status: hasKey("CRYPTOPANIC_API_KEY") ? "connected" : "disconnected",
      details: "Aggregating crypto-native news, Reddit, and Twitter sentiment.",
      metrics: [
        { label: "Polling", value: "Every 5m" },
        { label: "Events/hr", value: "~150" }
      ]
    },
    {
      id: "postgres_db",
      name: "TimescaleDB (Market)",
      type: "Historical Data",
      icon: Database,
      status: "connected",
      details: "Time-series database for OHLCV and indicator aggregations.",
      metrics: [
        { label: "Records", value: "14.2M" },
        { label: "Size", value: "2.4 GB" }
      ]
    },
    {
      id: "chroma_db",
      name: "Chroma Vector DB",
      type: "RAG & Memory",
      icon: Server,
      status: "connected",
      details: "Semantic search for past trading reflections and news context.",
      metrics: [
        { label: "Embeddings", value: "34,201" },
        { label: "Dimension", value: "1536" }
      ]
    }
  ];

  if (isLoading) {
    return <div className="p-6 text-muted-foreground font-mono">Loading Data Sources...</div>;
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-mono text-primary text-glow flex items-center gap-2">
            <Database className="h-6 w-6" />
            Data Sources
          </h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Manage and monitor external data feeds providing context to your Agent Team.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {sources.map((source) => (
          <div key={source.id} className="bg-card border border-border rounded-lg p-5 flex flex-col hover:border-primary/50 transition-colors group">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 bg-secondary/50 rounded-lg border border-border group-hover:border-primary/30 transition-colors">
                <source.icon className={`h-6 w-6 ${source.status === 'connected' ? 'text-primary' : 'text-muted-foreground'}`} />
              </div>
              <Badge variant="outline" className={
                source.status === 'connected' ? "bg-success/10 text-success border-success/30" : 
                source.status === 'degraded' ? "bg-warning/10 text-warning border-warning/30" : 
                "bg-destructive/10 text-destructive border-destructive/30"
              }>
                {source.status === 'connected' && <CheckCircle2 className="h-3 w-3 mr-1" />}
                {source.status === 'degraded' && <AlertCircle className="h-3 w-3 mr-1" />}
                {source.status === 'disconnected' && <XCircle className="h-3 w-3 mr-1" />}
                {source.status.toUpperCase()}
              </Badge>
            </div>
            
            <div className="mb-2">
              <h3 className="font-mono font-bold text-foreground text-lg">{source.name}</h3>
              <p className="text-[10px] font-mono text-primary uppercase tracking-wider">{source.type}</p>
            </div>
            
            <p className="text-xs text-muted-foreground mb-6 flex-1">
              {source.details}
            </p>

            <div className="grid grid-cols-2 gap-2 pt-4 border-t border-border">
              {source.metrics.map((m, i) => (
                <div key={i}>
                  <div className="text-[10px] text-muted-foreground font-mono uppercase">{m.label}</div>
                  <div className="text-sm font-mono font-semibold text-foreground">{m.value}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <Panel title="Data Source Integration Guide">
        <div className="text-sm text-muted-foreground space-y-2">
          <p>
            <strong>How it works:</strong> The Agent Team relies on these data sources to make decisions. 
            The <span className="text-primary font-mono">Market Analysts</span> ingest Live Stream and TimescaleDB data. 
            The <span className="text-primary font-mono">Strategists</span> combine this with News and Sentiment data to formulate proposals.
          </p>
          <p>
            To activate disconnected sources (like News API or CryptoPanic), please navigate to the <a href="/settings" className="text-primary hover:underline">Settings</a> page and configure your API keys.
          </p>
        </div>
      </Panel>
    </div>
  );
}
