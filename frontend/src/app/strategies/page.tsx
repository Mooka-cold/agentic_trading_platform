"use client";

import { SideNav } from "@/components/layout/SideNav";
import { Copy, Heart, MessageCircle, TrendingUp, Search } from "lucide-react";

export default function StrategiesPage() {
  return (
    <div className="flex h-screen bg-[#020617] text-slate-200 overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-[80px] min-w-[80px] border-r border-slate-800 bg-slate-900 flex flex-col items-center py-5 z-20">
        <SideNav />
      </div>
      
      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 border-b border-slate-800 flex items-center justify-between px-8 bg-slate-900 shrink-0">
           <div className="flex items-center gap-3">
              <TrendingUp className="text-blue-500" />
              <h1 className="font-bold text-lg text-white">Strategy Marketplace</h1>
           </div>
           <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
              <input 
                type="text" 
                placeholder="Search strategies..." 
                className="bg-slate-800 border border-slate-700 rounded-full pl-10 pr-4 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 w-64 transition-all"
              />
           </div>
        </header>

        <div className="flex-1 p-8 overflow-y-auto">
            <div className="max-w-6xl mx-auto">
                <div className="mb-8 text-center">
                    <h2 className="text-3xl font-bold text-white mb-2">Discover Top Strategies 🚀</h2>
                    <p className="text-slate-400">Clone and deploy algorithms from the best quant traders.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {STRATEGIES.map((strategy, i) => (
                        <StrategyCard key={i} {...strategy} />
                    ))}
                </div>
            </div>
        </div>
      </main>
    </div>
  );
}

const StrategyCard = ({ title, author, desc, tags, roi }: any) => (
  <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/10 transition-all group cursor-pointer flex flex-col h-full">
    <div className="flex justify-between items-start mb-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-slate-800 rounded-full overflow-hidden border border-slate-700">
           <img src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${author}`} alt={author} className="w-full h-full" />
        </div>
        <div>
            <span className="text-sm font-bold text-slate-200 block">{author}</span>
            <span className="text-[10px] text-slate-500 uppercase font-bold">Pro Trader</span>
        </div>
      </div>
      <div className="text-green-400 font-bold bg-green-900/20 border border-green-500/30 px-2 py-1 rounded-lg text-sm font-mono">
        +{roi}% ROI
      </div>
    </div>
    
    <h3 className="font-bold text-lg mb-2 text-white group-hover:text-blue-400 transition-colors">{title}</h3>
    <p className="text-sm text-slate-400 mb-6 line-clamp-3 leading-relaxed flex-1">{desc}</p>
    
    <div className="flex flex-wrap gap-2 mb-6">
      {tags.map((tag: string) => (
        <span key={tag} className="text-[10px] bg-slate-800 text-slate-400 border border-slate-700 px-2 py-1 rounded-md uppercase font-bold tracking-wider">#{tag}</span>
      ))}
    </div>

    <div className="flex justify-between items-center text-slate-500 border-t border-slate-800 pt-4 mt-auto">
      <div className="flex gap-4 text-xs font-bold">
        <button className="flex items-center gap-1.5 hover:text-red-400 transition-colors"><Heart size={14} /> 245</button>
        <button className="flex items-center gap-1.5 hover:text-blue-400 transition-colors"><MessageCircle size={14} /> 42</button>
      </div>
      <button className="text-blue-500 hover:bg-blue-900/30 p-2 rounded-full transition-colors">
        <Copy size={16} />
      </button>
    </div>
  </div>
);

const STRATEGIES = [
  {
    title: "BTC Trend Breakout + ATR Filter",
    author: "CryptoWizard",
    desc: "Trend following strategy based on Donchian Channel, combined with ATR to filter sideways markets. Excellent performance in 2023 backtests.",
    tags: ["Trend", "Low Freq", "BTC"],
    roi: 145
  },
  {
    title: "ETH/USDT Grid Arbitrage v2",
    author: "GridMaster",
    desc: "Grid strategy optimized for ETH oscillation, with adaptive grid spacing algorithm based on volatility.",
    tags: ["Grid", "Mid Freq", "ETH"],
    roi: 45
  },
  {
    title: "RSI Limit Reversal (5m)",
    author: "ScalperKing",
    desc: "Captures 5-minute level oversold rebounds. High win rate but low risk/reward ratio. Suitable for HFT.",
    tags: ["HFT", "RSI", "Reversal"],
    roi: 82
  },
  {
    title: "DCA Enhanced Edition",
    author: "HODLer",
    desc: "Increases investment when Fear & Greed Index is low, decreases when high. Best choice for long-term holders.",
    tags: ["DCA", "Long Term", "DeFi"],
    roi: 32
  },
];
