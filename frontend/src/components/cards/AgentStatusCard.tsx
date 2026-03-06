import React from 'react';
import { Bot, ShieldCheck, Activity, BrainCircuit } from 'lucide-react';

interface AgentStatusProps {
  name: string;
  role: string;
  status: 'idle' | 'thinking' | 'executing' | 'error';
  lastAction?: string;
  avatarColor: string;
}

export const AgentCard: React.FC<AgentStatusProps> = ({ name, role, status, lastAction, avatarColor }) => {
  const statusColors = {
    idle: 'bg-gray-400',
    thinking: 'bg-yellow-400 animate-pulse',
    executing: 'bg-green-500',
    error: 'bg-red-500',
  };

  return (
    <div className="bg-xiaohongshu-card p-5 rounded-3xl shadow-card flex items-start gap-4 border border-gray-50 hover:border-gray-100 transition-all">
      <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white shadow-md ${avatarColor}`}>
        {role === 'Strategist' && <BrainCircuit size={24} />}
        {role === 'Reviewer' && <ShieldCheck size={24} />}
        {role === 'Executor' && <Bot size={24} />}
      </div>
      
      <div className="flex-1">
        <div className="flex justify-between items-center mb-1">
          <h3 className="font-bold text-gray-800">{name}</h3>
          <span className={`w-2.5 h-2.5 rounded-full ${statusColors[status]}`} title={status} />
        </div>
        <p className="text-xs text-gray-500 mb-3 uppercase tracking-wider font-semibold">{role}</p>
        
        {status === 'thinking' ? (
          <div className="bg-gray-50 px-3 py-2 rounded-lg text-sm text-gray-600 italic animate-pulse">
            正在分析市场情绪...
          </div>
        ) : (
          <div className="text-sm text-gray-700 bg-gray-50 px-3 py-2 rounded-lg border border-gray-100">
            {lastAction || "等待指令..."}
          </div>
        )}
      </div>
    </div>
  );
};

export const AgentWorkflow: React.FC = () => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <AgentCard 
        name="Alice" 
        role="Strategist" 
        status="thinking" 
        lastAction="正在生成趋势策略..."
        avatarColor="bg-blue-500"
      />
      <AgentCard 
        name="Bob" 
        role="Reviewer" 
        status="idle" 
        lastAction="已通过风控审查 (Score: 92)"
        avatarColor="bg-purple-500"
      />
      <AgentCard 
        name="Charlie" 
        role="Executor" 
        status="executing" 
        lastAction="挂单 BTC/USDT @ 65420"
        avatarColor="bg-green-500"
      />
    </div>
  );
};
