"use client";

import { SideNav } from "@/components/layout/SideNav";
import { useState, useEffect } from "react";
import { Save, Settings as SettingsIcon, Bell, Key, Clock, Cpu, ShieldAlert } from "lucide-react";

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
  const [systemPrompt, setSystemPrompt] = useState("You are an expert crypto quant trader...");
  const [loading, setLoading] = useState(false);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const fetchConfigs = async () => {
        try {
            const res = await fetch(`${API_URL}/api/v1/system/config`);
            if (res.ok) {
                const configs = await res.json();
                const m = configs.find((c: any) => c.key === "LLM_MODEL");
                const r = configs.find((c: any) => c.key === "RISK_LEVEL");
                const p = configs.find((c: any) => c.key === "STRATEGIST_PROMPT");
                if (m) setModel(m.value);
                if (r) setRiskLevel(r.value);
                if (p) setSystemPrompt(p.value);
            }
        } catch (e) { console.error(e); }
    };
    fetchConfigs();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
        const tasks = [
            fetch(`${API_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "LLM_MODEL", value: model, description: "LLM Model Name" })
            }),
            fetch(`${API_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "RISK_LEVEL", value: riskLevel, description: "Risk Tolerance Level" })
            }),
            fetch(`${API_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "STRATEGIST_PROMPT", value: systemPrompt, description: "Strategist System Prompt" })
            })
        ];
        await Promise.all(tasks);
        await fetch(`${API_URL}/api/v1/system/reload`, { method: "POST" });
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
        <option value="deepseek-chat">DeepSeek Chat</option>
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
  const [enabled, setEnabled] = useState(false);
  const [interval, setInterval] = useState("1h");
  const [status, setStatus] = useState("Checking...");
  const [isRunning, setIsRunning] = useState(false);

  // Poll status
  useEffect(() => {
    const checkStatus = async () => {
        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/workflow/runner/status`);
            if (res.ok) {
                const data = await res.json();
                setIsRunning(data.is_running);
                setStatus(data.is_running ? "RUNNING" : "STOPPED");
            }
        } catch (e) {
            setStatus("UNKNOWN");
        }
    };
    checkStatus();
    const timer = window.setInterval(checkStatus, 5000);
    return () => clearInterval(timer);
  }, []);

  const handleStart = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/workflow/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: "BTC/USDT", session_id: "continuous-1" })
      });
      if (res.ok) alert("Started Continuous Mode");
    } catch (e) { alert("Failed to start"); }
  };

  const handleStop = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/workflow/stop`, {
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
  const [loading, setLoading] = useState(false);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const fetchConfigs = async () => {
        try {
            const res = await fetch(`${API_URL}/api/v1/system/config`);
            if (res.ok) {
                const configs = await res.json();
                const n = configs.find((c: any) => c.key === "NEWS_API_KEY");
                const t = configs.find((c: any) => c.key === "TWITTER_API_KEY");
                if (n) setNewsKey(n.value);
                if (t) setTwitterKey(t.value);
            }
        } catch (e) { console.error(e); }
    };
    fetchConfigs();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
        const tasks = [
            fetch(`${API_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "NEWS_API_KEY", value: newsKey, description: "News API Key" })
            }),
            fetch(`${API_URL}/api/v1/system/config`, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "TWITTER_API_KEY", value: twitterKey, description: "Twitter/X API Key" })
            })
        ];
        await Promise.all(tasks);
        await fetch(`${API_URL}/api/v1/system/reload`, { method: "POST" });
        alert("News settings saved & applied!");
    } catch (e) { alert("Failed to save"); } 
    finally { setLoading(false); }
  };

  return (
  <div className="space-y-4">
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
  const [cryptoPanicToken, setCryptoPanicToken] = useState("");
  const [loading, setLoading] = useState(false);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const fetchConfigs = async () => {
        try {
            const res = await fetch(`${API_URL}/api/v1/system/config`);
            if (res.ok) {
                const configs = await res.json();
                const openaiConfig = configs.find((c: any) => c.key === "OPENAI_API_KEY");
                const panicConfig = configs.find((c: any) => c.key === "CRYPTOPANIC_API_KEY");
                if (openaiConfig) setOpenaiKey(openaiConfig.value); // Warning: Plain text
                if (panicConfig) setCryptoPanicToken(panicConfig.value);
            }
        } catch (e) {
            console.error("Failed to load configs", e);
        }
    };
    fetchConfigs();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
        const tasks = [];
        if (openaiKey) {
            tasks.push(fetch(`${API_URL}/api/v1/system/config`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "OPENAI_API_KEY", value: openaiKey, description: "OpenAI API Key" })
            }));
        }
        if (cryptoPanicToken) {
            tasks.push(fetch(`${API_URL}/api/v1/system/config`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ key: "CRYPTOPANIC_API_KEY", value: cryptoPanicToken, description: "CryptoPanic API Token" })
            }));
        }
        await Promise.all(tasks);
        await fetch(`${API_URL}/api/v1/system/reload`, { method: "POST" });
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
      <label className="font-bold text-gray-300 text-sm">OpenAI API Key</label>
      <input 
        type="password" 
        value={openaiKey}
        onChange={(e) => setOpenaiKey(e.target.value)}
        className="w-full bg-[#020617] border border-slate-700 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 outline-none text-gray-300 font-mono text-sm"
        placeholder="sk-..." 
      />
    </div>
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
