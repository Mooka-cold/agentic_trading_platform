import { useState } from 'react';
import { Panel } from '@/components/shared/StatusBadge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { Save, Eye, EyeOff, Plus, Trash2, TestTube } from 'lucide-react';
import { toast } from 'sonner';

interface ModelConfig {
  id: string;
  agent: string;
  provider: string;
  model: string;
  apiKey: string;
  temperature: number;
  maxTokens: number;
}

interface DataSourceConfig {
  id: string;
  name: string;
  category: 'market' | 'macro' | 'onchain' | 'sentiment';
  apiKey: string;
  endpoint: string;
  enabled: boolean;
}

const defaultModels: ModelConfig[] = [
  { id: 'mc1', agent: 'analyst', provider: 'openai', model: 'gpt-4o', apiKey: '', temperature: 0.3, maxTokens: 4096 },
  { id: 'mc2', agent: 'bull_strategist', provider: 'openai', model: 'gpt-4o', apiKey: '', temperature: 0.5, maxTokens: 4096 },
  { id: 'mc3', agent: 'bear_strategist', provider: 'openai', model: 'gpt-4o', apiKey: '', temperature: 0.5, maxTokens: 4096 },
  { id: 'mc4', agent: 'portfolio_manager', provider: 'anthropic', model: 'claude-3.5-sonnet', apiKey: '', temperature: 0.2, maxTokens: 4096 },
  { id: 'mc5', agent: 'reviewer', provider: 'openai', model: 'gpt-4o', apiKey: '', temperature: 0.1, maxTokens: 4096 },
  { id: 'mc6', agent: 'reflector', provider: 'openai', model: 'gpt-4o-mini', apiKey: '', temperature: 0.4, maxTokens: 2048 },
];

const defaultDataSources: DataSourceConfig[] = [
  { id: 'ds1', name: 'Binance', category: 'market', apiKey: '', endpoint: 'wss://stream.binance.com', enabled: true },
  { id: 'ds2', name: 'CoinGecko', category: 'market', apiKey: '', endpoint: 'https://api.coingecko.com/api/v3', enabled: true },
  { id: 'ds3', name: 'FRED', category: 'macro', apiKey: '', endpoint: 'https://api.stlouisfed.org/fred', enabled: true },
  { id: 'ds4', name: 'Glassnode', category: 'onchain', apiKey: '', endpoint: 'https://api.glassnode.com/v1', enabled: true },
  { id: 'ds5', name: 'Dune Analytics', category: 'onchain', apiKey: '', endpoint: 'https://api.dune.com/api/v1', enabled: true },
  { id: 'ds6', name: 'LunarCrush', category: 'sentiment', apiKey: '', endpoint: 'https://lunarcrush.com/api4', enabled: true },
  { id: 'ds7', name: 'Twitter/X', category: 'sentiment', apiKey: '', endpoint: 'https://api.twitter.com/2', enabled: true },
];

const PROVIDERS = ['openai', 'anthropic', 'google', 'mistral', 'local'];
const MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o1-mini', 'o3-mini'],
  anthropic: ['claude-3.5-sonnet', 'claude-3.5-haiku', 'claude-3-opus'],
  google: ['gemini-2.0-flash', 'gemini-2.0-pro', 'gemini-1.5-pro'],
  mistral: ['mistral-large', 'mistral-medium', 'mistral-small'],
  local: ['llama-3.1-70b', 'llama-3.1-8b', 'qwen-2.5-72b'],
};

const AGENT_LABELS: Record<string, string> = {
  analyst: 'Chief Analyst',
  bull_strategist: 'Bull Strategist',
  bear_strategist: 'Bear Strategist',
  portfolio_manager: 'Portfolio Manager',
  reviewer: 'Risk Reviewer',
  reflector: 'Reflector',
};

function MaskedInput({ value, onChange, placeholder }: {
  value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pr-8 h-8 text-xs font-mono bg-secondary/50 border-border"
      />
      <button
        type="button"
        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
        onClick={() => setVisible(!visible)}
      >
        {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const [models, setModels] = useState<ModelConfig[]>(defaultModels);
  const [dataSources, setDataSources] = useState<DataSourceConfig[]>(defaultDataSources);
  const [activeTab, setActiveTab] = useState<'models' | 'datasources'>('models');

  const updateModel = (id: string, field: keyof ModelConfig, value: string | number) => {
    setModels(prev => prev.map(m => m.id === id ? { ...m, [field]: value } : m));
  };

  const updateDataSource = (id: string, field: keyof DataSourceConfig, value: string | boolean) => {
    setDataSources(prev => prev.map(d => d.id === id ? { ...d, [field]: value } : d));
  };

  const handleSave = () => {
    toast.success('Settings saved (mock — localStorage in production)');
  };

  const handleTest = (name: string) => {
    toast.info(`Testing connection to ${name}...`);
    setTimeout(() => toast.success(`${name} connection OK`), 1000);
  };

  return (
    <div className="space-y-4 animate-slide-in max-w-4xl">
      <div>
        <h1 className="text-xl font-mono font-bold text-foreground">Settings</h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5">Configure LLM models and data source API keys</p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2">
        {(['models', 'datasources'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-4 py-2 text-xs font-mono rounded border transition-colors',
              activeTab === tab
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border bg-card text-muted-foreground hover:text-foreground',
            )}
          >
            {tab === 'models' ? 'LLM Models' : 'Data Sources'}
          </button>
        ))}
        <div className="flex-1" />
        <Button size="sm" onClick={handleSave} className="gap-1.5 text-xs font-mono">
          <Save className="h-3.5 w-3.5" />
          Save All
        </Button>
      </div>

      {/* Models Tab */}
      {activeTab === 'models' && (
        <div className="space-y-3">
          {models.map((mc) => (
            <Panel key={mc.id} title={AGENT_LABELS[mc.agent] || mc.agent}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1 block">Provider</label>
                  <Select value={mc.provider} onValueChange={(v) => updateModel(mc.id, 'provider', v)}>
                    <SelectTrigger className="h-8 text-xs font-mono bg-secondary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PROVIDERS.map(p => <SelectItem key={p} value={p} className="text-xs font-mono">{p}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1 block">Model</label>
                  <Select value={mc.model} onValueChange={(v) => updateModel(mc.id, 'model', v)}>
                    <SelectTrigger className="h-8 text-xs font-mono bg-secondary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(MODELS[mc.provider] || []).map(m => <SelectItem key={m} value={m} className="text-xs font-mono">{m}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1 block">API Key</label>
                  <MaskedInput value={mc.apiKey} onChange={(v) => updateModel(mc.id, 'apiKey', v)} placeholder="sk-..." />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1 block">Temperature</label>
                    <Input
                      type="number" step={0.1} min={0} max={2}
                      value={mc.temperature}
                      onChange={(e) => updateModel(mc.id, 'temperature', parseFloat(e.target.value))}
                      className="h-8 text-xs font-mono bg-secondary/50"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1 block">Max Tokens</label>
                    <Input
                      type="number" step={512} min={256} max={32768}
                      value={mc.maxTokens}
                      onChange={(e) => updateModel(mc.id, 'maxTokens', parseInt(e.target.value))}
                      className="h-8 text-xs font-mono bg-secondary/50"
                    />
                  </div>
                </div>
              </div>
            </Panel>
          ))}
        </div>
      )}

      {/* Data Sources Tab */}
      {activeTab === 'datasources' && (
        <div className="space-y-3">
          {dataSources.map((ds) => (
            <Panel key={ds.id} title={ds.name} actions={
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleTest(ds.name)}
                  className="text-[10px] font-mono text-muted-foreground hover:text-foreground flex items-center gap-1"
                >
                  <TestTube className="h-3 w-3" /> Test
                </button>
                <button
                  onClick={() => updateDataSource(ds.id, 'enabled', !ds.enabled)}
                  className={cn(
                    'text-[10px] font-mono px-2 py-0.5 rounded border transition-colors',
                    ds.enabled ? 'border-success/30 text-success' : 'border-border text-muted-foreground',
                  )}
                >
                  {ds.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
            }>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1 block">Category</label>
                  <span className="text-xs font-mono text-foreground capitalize">{ds.category}</span>
                </div>
                <div>
                  <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1 block">Endpoint</label>
                  <Input
                    value={ds.endpoint}
                    onChange={(e) => updateDataSource(ds.id, 'endpoint', e.target.value)}
                    className="h-8 text-xs font-mono bg-secondary/50"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1 block">API Key</label>
                  <MaskedInput value={ds.apiKey} onChange={(v) => updateDataSource(ds.id, 'apiKey', v)} placeholder="Enter API key..." />
                </div>
              </div>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
