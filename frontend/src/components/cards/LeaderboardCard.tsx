import React from 'react';
import { Trophy, ArrowUpRight, Copy } from 'lucide-react';

interface StrategyProps {
  rank: number;
  name: string;
  author: string;
  roi: string;
  winRate: string;
  drawdown: string;
}

const StrategyRow: React.FC<StrategyProps> = ({ rank, name, author, roi, winRate, drawdown }) => (
  <div className="flex items-center p-4 hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-0">
    <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold mr-4 ${
      rank === 1 ? 'bg-yellow-100 text-yellow-600' : 
      rank === 2 ? 'bg-gray-100 text-gray-500' : 
      rank === 3 ? 'bg-orange-100 text-orange-600' : 'text-gray-400'
    }`}>
      {rank}
    </div>
    
    <div className="flex-1">
      <h4 className="font-bold text-gray-800">{name}</h4>
      <p className="text-xs text-gray-500">@{author}</p>
    </div>

    <div className="text-right px-4">
      <div className="text-green-600 font-bold flex items-center gap-1">
        <ArrowUpRight size={14} /> {roi}
      </div>
      <div className="text-xs text-gray-400">总收益</div>
    </div>

    <div className="text-right px-4 hidden md:block">
      <div className="font-medium text-gray-700">{winRate}</div>
      <div className="text-xs text-gray-400">胜率</div>
    </div>
    
    <button className="p-2 text-gray-400 hover:text-xiaohongshu-red hover:bg-red-50 rounded-full transition-colors">
      <Copy size={16} />
    </button>
  </div>
);

export const Leaderboard: React.FC = () => {
  return (
    <div className="bg-xiaohongshu-card rounded-3xl shadow-card overflow-hidden">
      <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-gradient-to-r from-red-50 to-white">
        <h2 className="text-xl font-bold flex items-center gap-2 text-gray-800">
          <Trophy className="text-yellow-500" /> 
          策略排行榜
        </h2>
        <span className="text-xs font-bold bg-white px-3 py-1 rounded-full text-xiaohongshu-red border border-red-100 shadow-sm">
          本周最热 🔥
        </span>
      </div>
      
      <div>
        <StrategyRow rank={1} name="SuperTrend AI Alpha" author="CryptoWizard" roi="+145%" winRate="68%" drawdown="-12%" />
        <StrategyRow rank={2} name="RSI Mean Reversion" author="QuantMaster" roi="+98%" winRate="55%" drawdown="-8%" />
        <StrategyRow rank={3} name="Breakout v3" author="Satoshi Nakamoto" roi="+82%" winRate="42%" drawdown="-15%" />
        <StrategyRow rank={4} name="Grid Trading Bot" author="SafeYield" roi="+45%" winRate="92%" drawdown="-5%" />
        <StrategyRow rank={5} name="DCA Accumulator" author="HODLer" roi="+32%" winRate="100%" drawdown="0%" />
      </div>
    </div>
  );
};
