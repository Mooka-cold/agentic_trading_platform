"use client";

import React, { useState } from 'react';
import { Send, Sparkles, Hash } from 'lucide-react';

export const PromptEditor: React.FC = () => {
  const [prompt, setPrompt] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  
  const handleAddTag = (tag: string) => {
    if (!tags.includes(tag)) setTags([...tags, tag]);
  };

  return (
    <div className="bg-xiaohongshu-card rounded-3xl p-6 shadow-card hover:shadow-hover transition-shadow duration-300 border border-xiaohongshu-border">  
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Sparkles className="text-xiaohongshu-red" size={20} />
          <span>创建策略 Prompt</span>
        </h2>
        <span className="text-sm text-xiaohongshu-textSecondary">{prompt.length}/500</span>
      </div>
      
      <textarea
        className="w-full h-32 bg-xiaohongshu-bg rounded-xl p-4 text-xiaohongshu-text resize-none focus:outline-none focus:ring-2 focus:ring-xiaohongshu-red transition-all placeholder-xiaohongshu-textSecondary"
        placeholder="写下你的交易灵感... 例如：当 BTC 突破 20 日均线且 RSI 低于 30 时买入..."
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />

      <div className="flex gap-2 mt-4 mb-6 overflow-x-auto pb-2">
        {['趋势跟踪', '均值回归', '高频', '网格'].map(tag => (
          <button 
            key={tag}
            onClick={() => handleAddTag(tag)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              tags.includes(tag) 
                ? 'bg-xiaohongshu-light text-xiaohongshu-red border border-xiaohongshu-red' 
                : 'bg-xiaohongshu-card text-xiaohongshu-text hover:bg-xiaohongshu-cardHover'
            }`}
          >
            #{tag}
          </button>
        ))}
      </div>

      <div className="flex justify-end gap-3">
        <button className="px-6 py-2.5 rounded-full bg-xiaohongshu-bg text-xiaohongshu-text font-medium hover:bg-xiaohongshu-card transition-colors">
          存草稿
        </button>
        <button className="px-8 py-2.5 rounded-full bg-xiaohongshu-red text-white font-bold shadow-lg shadow-xiaohongshu-red hover:bg-xiaohongshu-redHover transition-transform active:scale-95 flex items-center gap-2">
          <Send size={18} />
          发布并回测
        </button>
      </div>
    </div>
  );
};
