import { API_BASE_URL } from "./base";

export interface NewsItem {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  published_at: string;
  sentiment: string;
}

export const NewsAPI = {
  getLatestNews: async (limit: number = 20): Promise<NewsItem[]> => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/news/?limit=${limit}`);
      if (!res.ok) {
        console.error('API Error:', res.statusText);
        return [];
      }
      return await res.json();
    } catch (error) {
      console.error('Fetch Error:', error);
      return [];
    }
  }
};
