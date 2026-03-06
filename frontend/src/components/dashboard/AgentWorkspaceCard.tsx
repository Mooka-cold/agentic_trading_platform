"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, ShieldCheck, Zap } from "lucide-react";

export const AgentWorkspaceCard = () => {
  const [activeAgent, setActiveAgent] = useState<'strategist' | 'reviewer' | 'executor'>('strategist');
  const [message, setMessage] = useState("Thinking... I see a potential breakout on the 15m chart. RSI is cooling off, but volume is increasing.");

  // Simulate agent conversation
  useEffect(() => {
    const sequence = [
      { agent: 'strategist', msg: "Analyzing BTC 15m timeframe. RSI(14) = 32.5 (Oversold). Volume spike detected." },
      { agent: 'strategist', msg: "Detected bullish divergence on MACD. Signal strength: 0.75. Suggesting LONG." },
      { agent: 'reviewer', msg: "Checking risk parameters. Account exposure: 12%. Max DD: 2.1%. Approval needed." },
      { agent: 'reviewer', msg: "Risk Check PASSED. Risk Score: 15/100 (Safe). Proceed with caution." },
      { agent: 'executor', msg: "Placing LIMIT BUY order @ 64,220. Amount: 0.1 BTC..." },
      { agent: 'executor', msg: "Order FILLED at 64,218. Position opened." },
    ];

    let i = 0;
    const interval = setInterval(() => {
      const step = sequence[i % sequence.length];
      setActiveAgent(step.agent as any);
      setMessage(step.msg);
      i++;
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <div style={{ padding: '16px', borderBottom: '1px solid #f1f5f9', fontWeight: '700', fontSize: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#1e293b' }}>
        <span>Agent Workspace</span>
        <span style={{ fontSize: '12px', backgroundColor: '#dbeafe', color: '#1e40af', padding: '2px 8px', borderRadius: '12px', fontWeight: '600' }}>● Active</span>
      </div>

      <div style={{ flex: 1, padding: '20px', backgroundColor: '#f0f9ff', position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
        
        {/* Dialogue Bubble */}
        <div style={{ 
          position: 'absolute', 
          top: '20px', 
          left: '50%', 
          transform: 'translateX(-50%)', 
          backgroundColor: 'white', 
          padding: '12px 16px', 
          borderRadius: '12px', 
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)', 
          maxWidth: '80%', 
          width: '300px', 
          textAlign: 'center', 
          fontSize: '13px', 
          fontWeight: '500', 
          border: '1px solid #e2e8f0',
          transition: 'all 0.3s ease',
          zIndex: 10
        }}>
          {message}
          <div style={{ 
            position: 'absolute', 
            bottom: '-6px', 
            left: '50%', 
            width: '12px', 
            height: '12px', 
            backgroundColor: 'white', 
            transform: 'rotate(45deg) translateX(-50%)', 
            borderBottom: '1px solid #e2e8f0', 
            borderRight: '1px solid #e2e8f0' 
          }}></div>
        </div>

        {/* Agents Stage */}
        <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'flex-end', height: '120px' }}>
          
          <AgentCharacter 
            role="Strategist" 
            icon={<BrainCircuit size={24} color={activeAgent === 'strategist' ? '#3b82f6' : '#94a3b8'} />} 
            isActive={activeAgent === 'strategist'} 
            color="#3b82f6"
          />
          
          <AgentCharacter 
            role="Reviewer" 
            icon={<ShieldCheck size={24} color={activeAgent === 'reviewer' ? '#9333ea' : '#94a3b8'} />} 
            isActive={activeAgent === 'reviewer'} 
            color="#9333ea"
          />
          
          <AgentCharacter 
            role="Executor" 
            icon={<Zap size={24} color={activeAgent === 'executor' ? '#eab308' : '#94a3b8'} />} 
            isActive={activeAgent === 'executor'} 
            color="#eab308"
          />

        </div>
      </div>
    </>
  );
};

const AgentCharacter = ({ role, icon, isActive, color }: any) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative', width: '80px', transition: '0.3s', transform: isActive ? 'scale(1.1)' : 'scale(1)' }}>
    <div style={{ 
      width: '60px', 
      height: '60px', 
      borderRadius: '50%', 
      border: `3px solid ${isActive ? color : 'white'}`, 
      boxShadow: isActive ? `0 0 15px ${color}40` : '0 4px 6px rgba(0,0,0,0.1)', 
      backgroundColor: 'white', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center', 
      position: 'relative', 
      zIndex: 2 
    }}>
      {icon}
    </div>
    <div style={{ 
      width: '40px', 
      height: '30px', 
      backgroundColor: isActive ? color : '#cbd5e1', 
      borderRadius: '20px 20px 0 0', 
      marginTop: '-10px', 
      zIndex: 1 
    }}></div>
    <div style={{ 
      marginTop: '8px', 
      fontSize: '12px', 
      fontWeight: '700', 
      color: isActive ? color : '#475569', 
      backgroundColor: 'white', 
      padding: '2px 8px', 
      borderRadius: '10px', 
      boxShadow: '0 1px 2px rgba(0,0,0,0.1)' 
    }}>
      {role}
    </div>
  </div>
);
