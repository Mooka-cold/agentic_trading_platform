"use client";

import { SideNav } from "@/components/layout/SideNav";
import { Edit2, TrendingUp, Wallet, Clock, Settings, User } from "lucide-react";

export default function ProfilePage() {
  return (
    <div className="flex h-screen bg-[#020617] text-slate-200 overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-[80px] min-w-[80px] border-r border-slate-800 bg-slate-900 flex flex-col items-center py-5 z-20">
        <SideNav />
      </div>
      
      {/* Main Content */}
      <main className="flex-1 p-8 overflow-y-auto">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-3 text-white">
            <User size={28} className="text-blue-500" />
            User Profile
        </h1>

        {/* Profile Header */}
        <div className="bg-slate-900 rounded-2xl p-8 border border-slate-800 mb-8 flex flex-col md:flex-row items-center gap-8 shadow-xl">
          <div className="w-24 h-24 rounded-full bg-slate-800 overflow-hidden border-4 border-slate-700 shadow-lg relative shrink-0">
             <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix" alt="User" className="w-full h-full" />
             <button className="absolute bottom-0 right-0 bg-blue-600 p-1.5 rounded-full shadow-md text-white hover:bg-blue-700 transition-colors">
               <Edit2 size={12} />
             </button>
          </div>
          
          <div className="text-center md:text-left flex-1">
            <h1 className="text-2xl font-bold mb-2 text-white">Felix.Eth</h1>
            <p className="text-slate-400 mb-6 font-medium">Quant Trader | Trend Following | 3 Active Strategies</p>
            <div className="flex gap-8 justify-center md:justify-start">
              <StatItem label="Total ROI" value="+24.5%" color="text-green-400" />
              <StatItem label="Runtime" value="128 Days" />
              <StatItem label="Subscribers" value="42" />
            </div>
          </div>
          
          <div className="flex gap-3">
             <button className="px-6 py-2.5 border border-slate-600 rounded-xl font-bold text-slate-300 hover:bg-slate-800 transition-colors text-sm">Edit Profile</button>
             <button className="px-6 py-2.5 bg-blue-600 text-white rounded-xl font-bold shadow-lg shadow-blue-600/20 hover:bg-blue-700 transition-colors text-sm">Deposit / Withdraw</button>
          </div>
        </div>

        {/* My Strategies Grid */}
        <h2 className="text-xl font-bold mb-6 text-white flex items-center gap-2">
            <TrendingUp size={20} className="text-blue-500" />
            My Strategy Library
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <MyStrategyCard 
            title="BTC Grid Oscillation v1" 
            status="running" 
            roi="+12.4%" 
            pnl="+$342.50"
            lastRun="Just now"
          />
          <MyStrategyCard 
            title="ETH Trend Breakout Alpha" 
            status="stopped" 
            roi="-2.1%" 
            pnl="-$45.20"
            lastRun="2 hours ago"
          />
          <MyStrategyCard 
            title="Solana HFT Arb (Beta)" 
            status="backtesting" 
            roi="N/A" 
            pnl="N/A"
            lastRun="Backtesting..."
          />
          
          {/* Create New Card */}
          <div className="border-2 border-dashed border-slate-700 rounded-2xl p-6 flex flex-col items-center justify-center text-slate-500 hover:border-blue-500 hover:text-blue-500 hover:bg-slate-800/30 transition-all cursor-pointer h-56 group">
             <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mb-4 group-hover:bg-blue-500/20 group-hover:text-blue-500 transition-colors">
               <span className="text-2xl font-bold">+</span>
             </div>
             <span className="font-bold text-sm">Create New Strategy</span>
          </div>
        </div>
      </main>
    </div>
  );
}

const StatItem = ({ label, value, color = "text-white" }: any) => (
  <div className="text-center md:text-left">
    <div className={`text-xl font-bold ${color} mb-1`}>{value}</div>
    <div className="text-xs text-slate-500 uppercase font-bold tracking-wider">{label}</div>
  </div>
);

const MyStrategyCard = ({ title, status, roi, pnl, lastRun }: any) => {
  const statusConfig = {
    running: { color: "bg-green-900/30 text-green-400 border-green-500/30", label: "Running", icon: <ActivityIcon /> },
    stopped: { color: "bg-slate-800 text-slate-500 border-slate-700", label: "Stopped", icon: <StopIcon /> },
    backtesting: { color: "bg-yellow-900/30 text-yellow-400 border-yellow-500/30", label: "Backtesting", icon: <Clock size={12} /> },
  };
  
  const config = statusConfig[status as keyof typeof statusConfig];

  return (
    <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 hover:border-slate-600 transition-all cursor-pointer shadow-lg group h-56 flex flex-col">
      <div className="flex justify-between items-start mb-4">
        <div className={`px-2.5 py-1 rounded-md text-[10px] font-bold flex items-center gap-1.5 uppercase tracking-wide border ${config.color}`}>
          {config.icon} {config.label}
        </div>
        <button className="text-slate-600 hover:text-white transition-colors"><Settings size={16} /></button>
      </div>
      
      <h3 className="font-bold text-lg mb-auto text-slate-200 group-hover:text-blue-400 transition-colors">{title}</h3>
      
      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800/50">
        <div>
          <div className="text-[10px] text-slate-500 uppercase font-bold mb-1">ROI</div>
          <div className={`font-mono font-bold ${roi.startsWith('+') ? 'text-green-400' : roi.startsWith('-') ? 'text-red-400' : 'text-slate-400'}`}>{roi}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500 uppercase font-bold mb-1">PNL (USDT)</div>
          <div className={`font-mono font-bold ${pnl.startsWith('+') ? 'text-green-400' : pnl.startsWith('-') ? 'text-red-400' : 'text-slate-400'}`}>{pnl}</div>
        </div>
      </div>
      
      <div className="mt-4 text-[10px] text-slate-600 flex items-center gap-1.5 font-mono">
        <Clock size={10} /> Last run: {lastRun}
      </div>
    </div>
  );
};

const ActivityIcon = () => (
  <span className="relative flex h-2 w-2">
    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
  </span>
);

const StopIcon = () => (
  <span className="inline-block w-2 h-2 rounded-full bg-slate-500"></span>
);
