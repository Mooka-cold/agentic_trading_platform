"use client";

import { useEffect, useState } from "react";
import { NewsAPI, NewsItem } from "@/lib/api/news";

function timeAgo(dateString: string) {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  let interval = seconds / 31536000;
  if (interval > 1) return Math.floor(interval) + "y ago";
  interval = seconds / 2592000;
  if (interval > 1) return Math.floor(interval) + "mo ago";
  interval = seconds / 86400;
  if (interval > 1) return Math.floor(interval) + "d ago";
  interval = seconds / 3600;
  if (interval > 1) return Math.floor(interval) + "h ago";
  interval = seconds / 60;
  if (interval > 1) return Math.floor(interval) + "m ago";
  return Math.floor(seconds) + "s ago";
}

export const NewsFeedCard = () => {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  useEffect(() => {
    const fetchNews = async () => {
      try {
        const data = await NewsAPI.getLatestNews();
        setNews(data);
      } catch (error) {
        console.error("Failed to fetch news", error);
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
    // Refresh every 5 minutes
    const interval = setInterval(fetchNews, 300000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <div style={{ padding: '16px', borderBottom: '1px solid #f1f5f9', fontWeight: '700', fontSize: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#1e293b' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>Intelligence Feed</span>
          <span style={{ fontSize: '12px', backgroundColor: '#e0f2fe', color: '#0284c7', padding: '2px 8px', borderRadius: '12px', fontWeight: '600' }}>Live</span>
        </div>
        <button style={{ padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: '500', cursor: 'pointer', border: '1px solid #e2e8f0', background: 'white', color: '#475569' }}>
          Filter
        </button>
      </div>
      
      <div style={{ padding: '0', flex: 1, overflowY: 'auto' }}>
        {loading ? (
            <div style={{ padding: '16px', textAlign: 'center', color: '#6b7280' }}>Loading intelligence...</div>
        ) : news.map((item) => (
          <div 
            key={item.id} 
            style={{ 
              padding: '16px', 
              borderBottom: '1px solid #f1f5f9', 
              display: 'flex', 
              gap: '12px', 
              cursor: 'pointer', 
              transition: '0.2s',
              backgroundColor: hoveredId === item.id ? '#f8fafc' : 'transparent'
            }} 
            onMouseEnter={() => setHoveredId(item.id)}
            onMouseLeave={() => setHoveredId(null)}
            onClick={() => window.open(item.url, '_blank')}
          >
            <div style={{ width: '4px', borderRadius: '2px', flexShrink: 0, backgroundColor: item.sentiment === 'positive' ? '#22c55e' : item.sentiment === 'negative' ? '#ef4444' : '#94a3b8' }}></div>
            <div style={{ flex: 1 }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '4px', lineHeight: '1.4', color: '#1e293b' }}>{item.title}</h4>
              <div style={{ fontSize: '11px', color: '#64748b', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ backgroundColor: '#e2e8f0', padding: '2px 6px', borderRadius: '4px', fontWeight: '600' }}>{item.source}</span>
                <span>{timeAgo(item.published_at)}</span>
                <span style={{ color: item.sentiment === 'positive' ? '#16a34a' : item.sentiment === 'negative' ? '#dc2626' : '#64748b', fontWeight: '700' }}>
                  {item.sentiment ? item.sentiment.charAt(0).toUpperCase() + item.sentiment.slice(1) : 'Neutral'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
};
