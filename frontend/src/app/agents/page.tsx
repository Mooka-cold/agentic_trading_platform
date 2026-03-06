"use client";

import { AgentThinkingCard } from '@/components/dashboard/AgentThinkingCard';
import { SideNav } from '@/components/layout/SideNav';
import { BrainCircuit } from 'lucide-react';

export default function AgentsPage() {
  return (
    <div className="flex h-screen bg-[#020617] text-white overflow-hidden">
      {/* Sidebar */}
      <div className="w-[80px] min-w-[80px] border-r border-slate-800 bg-slate-900 flex flex-col items-center py-5 z-20">
        <SideNav />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* Top Bar */}
        <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900">
           <div className="flex items-center gap-3">
              <BrainCircuit className="text-blue-500" />
              <span className="font-bold text-lg">Agent Swarm & Portfolio</span>
           </div>
        </header>

        {/* Content */}
        <div className="flex-1 p-4 overflow-hidden">
          <AgentThinkingCard />
        </div>
      </div>
    </div>
  );
}
