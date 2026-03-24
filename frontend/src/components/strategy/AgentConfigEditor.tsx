"use client";

import { useState, useEffect } from "react";
import { PromptAPI } from "@/lib/api/prompt";
import { 
  Save, 
  RotateCcw, 
  CheckCircle2, 
  AlertCircle,
  BrainCircuit,
  LineChart,
  ShieldCheck,
  Activity
} from "lucide-react";
import { motion } from "framer-motion";

const AGENTS = [
  { id: "analyst", name: "The Analyst", icon: LineChart, color: "#3b82f6" },
  { id: "bull_strategist", name: "Bull Strategist", icon: BrainCircuit, color: "#8b5cf6" },
  { id: "bear_strategist", name: "Bear Strategist", icon: BrainCircuit, color: "#a855f7" },
  { id: "portfolio_manager", name: "Portfolio Manager", icon: BrainCircuit, color: "#c084fc" },
  { id: "reviewer", name: "The Reviewer", icon: ShieldCheck, color: "#ef4444" },
  { id: "reflector", name: "The Reflector", icon: Activity, color: "#10b981" },
];

export const AgentConfigEditor = () => {
  const [selectedAgentId, setSelectedAgentId] = useState("analyst");
  const [configContent, setConfigContent] = useState("");
  const [defaultPrompt, setDefaultPrompt] = useState("");
  const [configKey, setConfigKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const selectedAgent = AGENTS.find(a => a.id === selectedAgentId)!;

  useEffect(() => {
    loadConfig(selectedAgentId);
  }, [selectedAgentId]);

  const loadConfig = async (agentId: string) => {
    setLoading(true);
    try {
      const data = await PromptAPI.getConfig(agentId);
      setDefaultPrompt(String(data.default_prompt || ""));
      // Dynamically detect the config key
      const keys = Object.keys(data.config);
      if (keys.length > 0) {
          const key = keys[0];
          setConfigKey(key);
          setConfigContent(String(data.config[key]));
      } else {
          setConfigKey("config");
          setConfigContent("");
      }
      setStatus("idle");
    } catch (err) {
      console.error(err);
      setErrorMsg("Failed to load config");
      setStatus("error");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus("idle");
    try {
      if (!configKey) {
          throw new Error("Configuration key not found");
      }
      await PromptAPI.updateConfig(selectedAgentId, { [configKey]: configContent });
      setStatus("success");
      setTimeout(() => setStatus("idle"), 3000);
    } catch (err) {
      console.error(err);
      setErrorMsg("Failed to save config");
      setStatus("error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', height: '600px', backgroundColor: '#020617', borderRadius: '12px', overflow: 'hidden', border: '1px solid #1e293b' }}>
      
      {/* Sidebar - Agent Selector */}
      <div style={{ width: '240px', backgroundColor: '#0f172a', borderRight: '1px solid #1e293b', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '20px', borderBottom: '1px solid #1e293b' }}>
            <h2 style={{ color: '#e2e8f0', fontWeight: 'bold', fontSize: '16px' }}>Strategy Lab</h2>
            <p style={{ color: '#64748b', fontSize: '12px', marginTop: '4px' }}>Configure Agent Personas</p>
        </div>
        <div style={{ flex: 1, padding: '12px' }}>
            {AGENTS.map(agent => (
                <div 
                    key={agent.id}
                    onClick={() => setSelectedAgentId(agent.id)}
                    style={{ 
                        padding: '12px', 
                        borderRadius: '8px', 
                        marginBottom: '8px',
                        cursor: 'pointer',
                        backgroundColor: selectedAgentId === agent.id ? '#1e293b' : 'transparent',
                        border: selectedAgentId === agent.id ? `1px solid ${agent.color}40` : '1px solid transparent',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        transition: 'all 0.2s'
                    }}
                >
                    <agent.icon size={18} color={selectedAgentId === agent.id ? agent.color : '#64748b'} />
                    <span style={{ 
                        color: selectedAgentId === agent.id ? 'white' : '#94a3b8', 
                        fontWeight: selectedAgentId === agent.id ? '600' : '400',
                        fontSize: '14px'
                    }}>
                        {agent.name}
                    </span>
                </div>
            ))}
        </div>
      </div>

      {/* Main Content - Editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#020617' }}>
        
        {/* Editor Header */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: selectedAgent.color, boxShadow: `0 0 8px ${selectedAgent.color}` }}></div>
                <h3 style={{ color: 'white', fontWeight: 'bold' }}>{selectedAgent.name} Configuration</h3>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                {status === 'success' && (
                    <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#22c55e', fontSize: '13px' }}>
                        <CheckCircle2 size={16} /> Saved
                    </motion.div>
                )}
                {status === 'error' && (
                    <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#ef4444', fontSize: '13px' }}>
                        <AlertCircle size={16} /> {errorMsg}
                    </motion.div>
                )}
                
                <button 
                    onClick={() => loadConfig(selectedAgentId)}
                    disabled={loading || saving}
                    style={{ padding: '8px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: 'transparent', color: '#94a3b8', cursor: 'pointer' }}
                    title="Reset to Saved"
                >
                    <RotateCcw size={16} />
                </button>
                
                <button 
                    onClick={handleSave}
                    disabled={loading || saving}
                    style={{ 
                        padding: '8px 16px', 
                        borderRadius: '6px', 
                        backgroundColor: '#4f46e5', 
                        color: 'white', 
                        fontWeight: '600', 
                        fontSize: '13px',
                        border: 'none',
                        cursor: saving ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        opacity: saving ? 0.7 : 1
                    }}
                >
                    {saving ? (
                        <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}>
                             <Activity size={16} />
                        </motion.div>
                    ) : (
                        <Save size={16} />
                    )}
                    {saving ? 'Saving...' : 'Save Config'}
                </button>
            </div>
        </div>

        {/* Editor Area */}
        <div style={{ flex: 1, position: 'relative' }}>
            {loading ? (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}>
                        <Activity size={24} />
                    </motion.div>
                </div>
            ) : (
                <textarea
                    value={configContent}
                    onChange={(e) => setConfigContent(e.target.value)}
                    style={{
                        width: '100%',
                        height: '100%',
                        backgroundColor: '#020617',
                        color: '#cbd5e1',
                        padding: '24px',
                        border: 'none',
                        outline: 'none',
                        fontFamily: 'monospace',
                        fontSize: '14px',
                        lineHeight: '1.6',
                        resize: 'none'
                    }}
                    spellCheck={false}
                />
            )}
        </div>

        <div style={{ borderTop: '1px solid #1e293b', backgroundColor: '#0b1220' }}>
            <div style={{ padding: '10px 24px', color: '#94a3b8', fontSize: '12px', fontWeight: 600 }}>
                Default Prompt (Read-only)
            </div>
            <div style={{ padding: '0 24px 16px 24px' }}>
                <textarea
                    value={defaultPrompt}
                    readOnly
                    style={{
                        width: '100%',
                        height: '180px',
                        backgroundColor: '#020617',
                        color: '#94a3b8',
                        padding: '14px',
                        border: '1px solid #1e293b',
                        borderRadius: '8px',
                        outline: 'none',
                        fontFamily: 'monospace',
                        fontSize: '12px',
                        lineHeight: '1.55',
                        resize: 'none'
                    }}
                    spellCheck={false}
                />
            </div>
        </div>
        
        {/* Footer Info */}
        <div style={{ padding: '8px 24px', borderTop: '1px solid #1e293b', backgroundColor: '#0f172a', color: '#64748b', fontSize: '12px' }}>
            Supports Markdown format. Changes affect the Agent&apos;s persona immediately.
        </div>

      </div>
    </div>
  );
};
