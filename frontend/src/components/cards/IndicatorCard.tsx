import React from 'react';
import { Gauge, TrendingUp, TrendingDown, Activity } from 'lucide-react';

interface IndicatorProps {
  label: string;
  value: string | number;
  trend?: 'up' | 'down' | 'neutral';
  color?: string;
  subtext?: string;
}

const IndicatorCard: React.FC<IndicatorProps> = ({ label, value, trend, color = 'text-xiaohongshu-text', subtext }) => (
  <div className="bg-xiaohongshu-card p-4 rounded-2xl shadow-sm border border-gray-100 flex flex-col justify-between h-32 hover:shadow-md transition-shadow">
    <div className="flex justify-between items-start">
      <span className="text-sm font-medium text-gray-400 uppercase tracking-wide">{label}</span>
      {trend === 'up' && <TrendingUp size={18} className="text-green-500" />}
      {trend === 'down' && <TrendingDown size={18} className="text-red-500" />}
    </div>
    
    <div className="mt-2">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      {subtext && <div className="text-xs text-gray-400 mt-1">{subtext}</div>}
    </div>
  </div>
);

export const IndicatorDashboard: React.FC = () => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <IndicatorCard 
        label="RSI (14)" 
        value="72.4" 
        trend="up" 
        color="text-xiaohongshu-red" 
        subtext="超买区域"
      />
      <IndicatorCard 
        label="MACD" 
        value="+120.5" 
        trend="up" 
        color="text-green-600" 
        subtext="金叉形成"
      />
      <IndicatorCard 
        label="Fear & Greed" 
        value="65" 
        trend="neutral" 
        color="text-orange-500" 
        subtext="贪婪"
      />
      <IndicatorCard 
        label="Volatility" 
        value="High" 
        trend="down" 
        color="text-purple-600" 
        subtext="ATR: 1450"
      />
    </div>
  );
};
