"use client";

import { SideNav } from "@/components/layout/SideNav";
import { useState, useEffect } from "react";
import { Save, Settings as SettingsIcon, Bell, Key, Clock, Cpu, ShieldAlert } from "lucide-react";
import { API_BASE_URL } from "@/lib/api/base";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("agent");

  return (
    <div className="flex h-screen bg-[#020617] text-slate-200 overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-[80px] min-w-[80px] border-r border-slate-800 bg-slate-900 flex flex-col items-center py-5 z-20">
        <SideNav />
      </div>
      
      {/* Main Content */}
      <main className="flex-1 p-8 overflow-y-auto">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-3 text-white">
            <SettingsIcon size={28} className="text-blue-500" />
            System Settings
        </h1>

        <div className="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden max-w-4xl shadow-xl">
          {/* Tabs */}
          <div className="flex border-b border-slate-800">
            <TabButton icon={<Cpu size={16}/>} label="Agent Config" active={activeTab === "agent"} onClick={() => setActiveTab("agent")} />
            <TabButton icon={<Clock size={16}/>} label="Schedule" active={activeTab === "schedule"} onClick={() => setActiveTab("schedule")} />
            <TabButton icon={<Bell size={16}/>} label="News Sources" active={activeTab === "news"} onClick={() => setActiveTab("news")} />
            <TabButton icon={<Key size={16}/>} label="API Keys" active={activeTab === "api"} onClick={() => setActiveTab("api")} />
          </div>

          <div className="p-8">
            {activeTab === "agent" && <AgentSettings />}
            {activeTab === "schedule" && <ScheduleSettings />}
            {activeTab === "news" && <NewsSettings />}
            {activeTab === "api" && <ApiSettings />}
          </div>
        </div>
      </main>
    </div>
  );
}

const TabButton = ({ icon, label, active, onClick }: { icon: any, label: string, active: boolean, onClick: () => void }) => (
  <button 
    onClick={onClick}
    className={`
      flex-1 p-4 flex items-center justify-center gap-2 
      transition-all text-sm font-medium border-b-2
      ${active 
        ? 'bg-slate-800 text-blue-400 border-blue-500' 
        : 'text-slate-400 border-transparent hover:text-slate-200 hover:bg-slate-800/50'}
    `}
  >
    {icon}
    {label}
  </button>
);

const AgentSettings = () => {
  const [model, setModel] = useState("gpt-4-turbo");
  const [riskLevel, setRiskLevel] = useState("medium");
  const [outputLanguage, setOutputLanguage] = useState("zh");
  const [sentimentWindowHours, setSentimentWindowHours] = useState("6");
  const [systemPrompt, setSystemPrompt] = useState("You are an expert crypto quant trader...");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchConfigs = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/system/config`);
            if (res.ok) {
                const configs = await res.json();
                const m = configs.find((c: any) => c.key === "LLM_MODEL");
                const r = configs.find((c: any) => c.key === "RISK_LEVEL");
                const p = configs.find((c: any) => c.key === "STRATEGIST_PROMPT");
                const l = configs.find((c: any) => c.key === "AGENT_OUTPUT_LANGUAGE");
                const s = configs.find((c: any) => c.key === "SENTIMENT_NEWS_WINDOW_HOURS");
                if (m) setModel(m.value);
                if (r) setRiskLevel(r.value);
                if (p) setSystemPrompt(p.value);
                if (l) setOutputLanguage(l.value);
                if (s && s.value) setSentimentWindowHours(s.value);
            }
        } catch (e) { console.error(e); }
    };
    fetchConfigs();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
        const tasks = [
            fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "LLM_MODEL", value: model, description: "LLM Model Name" })
            }),
            fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "RISK_LEVEL", value: riskLevel, description: "Risk Tolerance Level" })
            }),
            fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "STRATEGIST_PROMPT", value: systemPrompt, description: "Strategist System Prompt" })
            }),
            fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "AGENT_OUTPUT_LANGUAGE", value: outputLanguage, description: "Agent Output Language" })
            }),
            fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                  key: "SENTIMENT_NEWS_WINDOW_HOURS",
                  value: String(Math.min(72, Math.max(1, Number(sentimentWindowHours) || 6))),
                  description: "Sentiment News Lookback Window Hours"
                })
            })
        ];
        await Promise.all(tasks);
        await fetch(`${API_BASE_URL}/api/v1/system/reload`, { method: "POST" });
        alert("Agent settings saved & applied!");
    } catch (e) { alert("Failed to save"); } 
    finally { setLoading(false); }
  };

  return (
  <div className="space-y-8">
    <div className="space-y-3">
      <label className="font-bold text-gray-200 flex items-center gap-2">
        <Cpu size={16} className="text-blue-500" />
        LLM Model
      </label>
      <p className="text-sm text-gray-500">Select the underlying model for reasoning.</p>
      <select 
        value={model}
        onChange={(e) => setModel(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm appearance-none cursor-pointer"
      >
        <option value="gpt-4-turbo">GPT-4 Turbo</option>
        <option value="gpt-4o">GPT-4o</option>
        <option value="claude-3-opus">Claude 3 Opus</option>
        <option disabled>--- Qwen (Aliyun) ---</option>
        <option value="qwen-plus">Qwen Plus</option>
        <option value="qwen-turbo">Qwen Turbo</option>
        <option value="qwen-long">Qwen Long</option>
        <option disabled>--- DeepSeek ---</option>
        <option value="deepseek-chat">DeepSeek Chat</option>
        <option value="deepseek-reasoner">DeepSeek Reasoner</option>
      </select>
    </div>

    <div className="space-y-3">
      <label className="font-bold text-gray-200 flex items-center gap-2">
        <Cpu size={16} className="text-green-500" />
        Agent Output Language
      </label>
      <p className="text-sm text-gray-500">Select the language for all agent outputs.</p>
      <select
        value={outputLanguage}
        onChange={(e) => setOutputLanguage(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm appearance-none cursor-pointer"
      >
        <option value="zh">中文</option>
        <option value="en">English</option>
      </select>
    </div>

    <div className="space-y-3">
      <label className="font-bold text-gray-200 flex items-center gap-2">
        <Cpu size={16} className="text-purple-500" />
        Strategist System Prompt
      </label>
      <p className="text-sm text-gray-500">Define the persona and core logic for the Strategy Agent.</p>
      <textarea 
        value={systemPrompt}
        onChange={(e) => setSystemPrompt(e.target.value)}
        className="w-full h-40 bg-[#020617] border border-slate-700 rounded-xl p-4 focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm text-gray-300 resize-none"
      />
    </div>

    <div className="space-y-3">
      <label className="font-bold text-gray-200 flex items-center gap-2">
        <Clock size={16} className="text-cyan-500" />
        Sentiment News Window (Hours)
      </label>
      <p className="text-sm text-gray-500">Only use news within this time window for sentiment scoring.</p>
      <input
        type="number"
        min={1}
        max={72}
        step={1}
        value={sentimentWindowHours}
        onChange={(e) => setSentimentWindowHours(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm"
      />
    </div>

    <div className="space-y-3">
      <label className="font-bold text-gray-200 flex items-center gap-2">
        <ShieldAlert size={16} className="text-red-500" />
        Risk Level
      </label>
      <p className="text-sm text-gray-500">Set the global risk tolerance.</p>
      <select 
        value={riskLevel}
        onChange={(e) => setRiskLevel(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm appearance-none cursor-pointer"
      >
        <option value="low">Low (Conservative)</option>
        <option value="medium">Medium (Balanced)</option>
        <option value="high">High (Aggressive)</option>
      </select>
    </div>
    <SaveButton onClick={handleSave} loading={loading} />
  </div>
  );
};

const ScheduleSettings = () => {
  const [interval, setInterval] = useState("1h");
  const [status, setStatus] = useState("Checking...");
  const [isRunning, setIsRunning] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [sessionId, setSessionId] = useState("");

  // Poll status
  useEffect(() => {
    let cancelled = false;
    const fetchSymbols = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/market/symbols`);
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && Array.isArray(data.symbols) && data.symbols.length > 0) {
          setSymbol((prev) => (prev && data.symbols.includes(prev) ? prev : data.symbols[0]));
        }
      } catch (e) {
        console.error("Load symbols failed", e);
      }
    };
    fetchSymbols();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const checkStatus = async () => {
        try {
            const apiUrl = API_BASE_URL;
            const res = await fetch(`${apiUrl}/api/v1/workflow/runner/status`);
            if (res.ok) {
                const data = await res.json();
                setIsRunning(data.is_running);
                setStatus(data.is_running ? "RUNNING" : "STOPPED");
            } else {
                setStatus("ERROR");
            }
        } catch (e) {
            console.error("Status check failed", e);
            setStatus("UNKNOWN");
        }
    };
    checkStatus();
    const timer = window.setInterval(checkStatus, 5000);
    return () => clearInterval(timer);
  }, []);

  const handleStart = async () => {
    try {
      const apiUrl = API_BASE_URL;
      const normalizedSymbol = (symbol || "").trim();
      if (!normalizedSymbol) {
        alert("请先选择或输入交易对");
        return;
      }
      const normalizedSessionId = (sessionId || `continuous-${Date.now()}`).trim() || `continuous-${Date.now()}`;
      const res = await fetch(`${apiUrl}/api/v1/workflow/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: normalizedSymbol, session_id: normalizedSessionId })
      });
      if (res.ok) alert("Started Continuous Mode");
    } catch (e) { alert("Failed to start"); }
  };

  const handleStop = async () => {
    try {
      const apiUrl = API_BASE_URL;
      const res = await fetch(`${apiUrl}/api/v1/workflow/stop`, {
        method: "POST"
      });
      if (res.ok) alert("Stopped Continuous Mode");
    } catch (e) { alert("Failed to stop"); }
  };

  return (
    <div className="space-y-6">
        <div className="flex justify-between items-center p-5 bg-[#020617] rounded-xl border border-slate-700">
            <div>
                <h3 className="font-bold text-white mb-1">Continuous Mode (AI Loop)</h3>
                <p className="text-sm text-gray-500">Run AI analysis & trading loop in background.</p>
            </div>
            <div className="flex items-center gap-4">
                <span className={`text-xs font-bold px-3 py-1.5 rounded border ${isRunning ? 'bg-green-900/30 text-green-400 border-green-500/30' : 'bg-slate-800 text-slate-400 border-slate-700'}`}>
                    {status}
                </span>
                
                {!isRunning ? (
                    <button 
                        onClick={handleStart}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg font-bold text-sm transition-colors shadow-lg shadow-green-600/20"
                    >
                        Start Loop
                    </button>
                ) : (
                    <button 
                        onClick={handleStop}
                        className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg font-bold text-sm transition-colors shadow-lg shadow-red-600/20"
                    >
                        Stop Loop
                    </button>
                )}
            </div>
        </div>

        <div className="border-t border-slate-800 my-6"></div>

        {/* Legacy Schedule Config (Optional) */}
        <div className="space-y-3">
            <h3 className="font-bold text-white mb-2 text-sm">Loop Runtime Parameters</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <input
                    className="bg-[#020617] border border-slate-700 rounded-lg p-2 text-sm text-slate-200"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    placeholder="BTC/USDT"
                />
                <input
                    className="bg-[#020617] border border-slate-700 rounded-lg p-2 text-sm text-slate-200"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    placeholder="continuous-<timestamp>"
                />
            </div>
        </div>
        <div className="opacity-50 pointer-events-none">
            <h3 className="font-bold text-white mb-2 text-sm">Legacy Scheduler Config</h3>
            <div className="flex gap-4">
                <select 
                    className="bg-[#020617] border border-slate-700 rounded-lg p-2 text-sm text-slate-400"
                    value={interval}
                    onChange={(e) => setInterval(e.target.value)}
                >
                    <option value="15m">15 Minutes</option>
                    <option value="1h">1 Hour</option>
                </select>
            </div>
        </div>
    </div>
  );
};

const NewsSettings = () => {
  const [newsKey, setNewsKey] = useState("");
  const [twitterKey, setTwitterKey] = useState("");
  const [cryptoPanicToken, setCryptoPanicToken] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchConfigs = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/system/config`);
            if (res.ok) {
                const configs = await res.json();
                const n = configs.find((c: any) => c.key === "NEWS_API_KEY");
                const t = configs.find((c: any) => c.key === "TWITTER_API_KEY");
                const c = configs.find((c: any) => c.key === "CRYPTOPANIC_API_KEY");
                if (n) setNewsKey(n.value);
                if (t) setTwitterKey(t.value);
                if (c) setCryptoPanicToken(c.value);
            }
        } catch (e) { console.error(e); }
    };
    fetchConfigs();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
        const tasks = [
            fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "NEWS_API_KEY", value: newsKey, description: "News API Key" })
            }),
            fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "TWITTER_API_KEY", value: twitterKey, description: "Twitter/X API Key" })
            }),
            fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "CRYPTOPANIC_API_KEY", value: cryptoPanicToken, description: "CryptoPanic API Token" })
            })
        ];
        await Promise.all(tasks);
        await fetch(`${API_BASE_URL}/api/v1/system/reload`, { method: "POST" });
        alert("News settings saved & applied!");
    } catch (e) { alert("Failed to save"); } 
    finally { setLoading(false); }
  };

  return (
  <div className="space-y-4">
    <div className="space-y-2">
      <label className="font-bold text-gray-300 text-sm">CryptoPanic API Token</label>
      <input 
        type="password" 
        value={cryptoPanicToken}
        onChange={(e) => setCryptoPanicToken(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm"
        placeholder="Auth Token" 
      />
    </div>
    <div className="space-y-2">
      <label className="font-bold text-gray-300 text-sm">NewsAPI Key</label>
      <input 
        type="password" 
        value={newsKey}
        onChange={(e) => setNewsKey(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm"
        placeholder="Enter API Key" 
      />
    </div>
    <div className="space-y-2">
      <label className="font-bold text-gray-300 text-sm">Twitter/X API Key</label>
      <input 
        type="password" 
        value={twitterKey}
        onChange={(e) => setTwitterKey(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm"
        placeholder="Enter API Key" 
      />
    </div>
    <div className="pt-4">
        <SaveButton onClick={handleSave} loading={loading} />
    </div>
  </div>
  );
};

const ApiSettings = () => {
  const [openaiKey, setOpenaiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchConfigs = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/system/config`);
            if (res.ok) {
                const configs = await res.json();
                const openaiConfig = configs.find((c: any) => c.key === "OPENAI_API_KEY");
                const baseConfig = configs.find((c: any) => c.key === "OPENAI_API_BASE");
                if (openaiConfig) setOpenaiKey(openaiConfig.value);
                if (baseConfig) setBaseUrl(baseConfig.value);
            }
        } catch (e) { console.error(e); }
    };
    fetchConfigs();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
        const tasks = [];
        if (openaiKey) {
            tasks.push(fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "OPENAI_API_KEY", value: openaiKey, description: "OpenAI API Key" })
            }));
        }
        if (baseUrl) {
            tasks.push(fetch(`${API_BASE_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "OPENAI_API_BASE", value: baseUrl, description: "OpenAI Compatible Base URL" })
            }));
        }
        await Promise.all(tasks);
        await fetch(`${API_BASE_URL}/api/v1/system/reload`, { method: "POST" });
        alert("Settings saved & applied!");
    } catch (e) {
        alert("Failed to save settings.");
    } finally {
        setLoading(false);
    }
  };

  return (
  <div className="space-y-6">
    <div className="space-y-2">
      <label className="font-bold text-gray-300 text-sm">OpenAI Compatible Base URL</label>
      <input 
        type="text" 
        value={baseUrl}
        onChange={(e) => setBaseUrl(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm"
        placeholder="https://api.openai.com/v1" 
      />
      <p className="text-xs text-gray-500">For Qwen/DeepSeek, use their API endpoint (e.g. https://dashscope.aliyuncs.com/compatible-mode/v1)</p>
    </div>

    <div className="space-y-2">
      <label className="font-bold text-gray-300 text-sm">API Key</label>
      <input 
        type="password" 
        value={openaiKey}
        onChange={(e) => setOpenaiKey(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm"
        placeholder="sk-..." 
      />
    </div>
    <div className="pt-4">
        <SaveButton onClick={handleSave} loading={loading} />
    </div>
  </div>
  );
};

const SaveButton = ({ onClick, loading }: { onClick?: () => void, loading?: boolean }) => (
  <button 
    onClick={onClick}
    disabled={loading}
    className={`bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg font-bold transition-colors flex items-center gap-2 shadow-lg shadow-blue-600/20 ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
  >
    <Save size={18} /> {loading ? "Saving..." : "Save Changes"}
  </button>
);
