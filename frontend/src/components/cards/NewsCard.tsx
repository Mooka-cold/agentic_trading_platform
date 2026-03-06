import React from 'react';
import { Heart, MessageCircle, Share2, TrendingUp, TrendingDown } from 'lucide-react';

interface NewsCardProps {
  title: string;
  source: string;
  time: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  imageUrl?: string;
  summary: string;
}

const NewsCard: React.FC<NewsCardProps> = ({ title, source, time, sentiment, imageUrl, summary }) => {
  return (
    <div className="bg-xiaohongshu-card rounded-card overflow-hidden shadow-card hover:shadow-hover transition-all duration-300 break-inside-avoid mb-4">
      {imageUrl && (
        <div className="relative h-32 w-full overflow-hidden bg-gray-200">
          <img 
            src={imageUrl} 
            alt={title} 
            className="h-full w-full object-cover transition-transform duration-300 hover:scale-105" 
            style={{ objectFit: 'cover', height: '100%', width: '100%' }} // Inline style fallback
          />
          <div className="absolute top-2 right-2 bg-black/50 text-white text-xs px-2 py-1 rounded-full backdrop-blur-sm">
            {source}
          </div>
        </div>
      )}
      
      <div className="p-4">
        <div className="flex items-center gap-2 mb-2">
          {sentiment === 'bullish' && <span className="text-xs font-bold text-green-600 bg-green-50 px-2 py-0.5 rounded-md">利好</span>}
          {sentiment === 'bearish' && <span className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-md">利空</span>}
          <span className="text-xs text-gray-400">{time}</span>
        </div>
        
        <h3 className="font-bold text-gray-800 mb-2 leading-snug line-clamp-2">{title}</h3>
        <p className="text-sm text-gray-500 line-clamp-3 mb-4">{summary}</p>
        
        <div className="flex justify-between items-center text-gray-400">
          <div className="flex gap-4">
            <button className="flex items-center gap-1 hover:text-xiaohongshu-red transition-colors">
              <Heart size={16} /> <span className="text-xs">124</span>
            </button>
            <button className="flex items-center gap-1 hover:text-blue-500 transition-colors">
              <MessageCircle size={16} /> <span className="text-xs">18</span>
            </button>
          </div>
          <Share2 size={16} className="cursor-pointer hover:text-gray-600" />
        </div>
      </div>
    </div>
  );
};

export const NewsFeed: React.FC = () => {
  const news = [
    {
      title: "Bitcoin ETF 净流入创新高，BlackRock 持续增持",
      source: "CoinDesk",
      time: "10分钟前",
      sentiment: "bullish",
      imageUrl: "https://images.unsplash.com/photo-1518546305927-5a555bb7020d?q=80&w=2969&auto=format&fit=crop",
      summary: "据最新数据，IBIT 单日流入超过 5 亿美元，显示机构投资者对加密市场的信心正在恢复..."
    },
    {
      title: "美联储暗示可能在 9 月降息",
      source: "Bloomberg",
      time: "1小时前",
      sentiment: "bullish",
      summary: "鲍威尔在最新的讲话中提到通胀已得到控制，市场普遍预期这是货币政策转向的明确信号..."
    },
    {
      title: "某交易所发生安全漏洞，约 2000 万美元资产被盗",
      source: "The Block",
      time: "2小时前",
      sentiment: "bearish",
      summary: "黑客利用智能合约漏洞攻击了热钱包，目前团队已暂停提币并展开调查..."
    },
  ] as const;

  return (
    <div className="columns-1 md:columns-2 lg:columns-3 gap-4 space-y-4">
      {news.map((item, i) => (
        <NewsCard key={i} {...item} />
      ))}
    </div>
  );
};
