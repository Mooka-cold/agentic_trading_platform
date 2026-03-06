import httpx
from sqlalchemy.orm import Session
from app.models.news import News
from app.core.config import settings
from datetime import datetime

class NewsService:
    def __init__(self):
        self.api_key = settings.NEWS_API_KEY
        self.api_url = "https://newsapi.org/v2/everything"

    async def fetch_and_store_news(
        self,
        db: Session,
        symbol: str = "BTC",
        query: str | None = None,
        domains: str | None = None,
        page_size: int = 20
    ) -> int:
        if not self.api_key:
            print("Warning: NEWS_API_KEY not set.")
            return 0
            
        query_keyword = query or settings.NEWSAPI_QUERY
        if not query_keyword:
            if "ETH" in symbol:
                query_keyword = "ethereum"
            elif "SOL" in symbol:
                query_keyword = "solana"
            else:
                query_keyword = "crypto OR bitcoin OR stablecoin OR regulation OR ETF OR hack OR exploit"
        
        try:
            params = {
                "q": query_keyword,
                "searchIn": "title,description",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "apiKey": self.api_key
            }
            domain_value = domains or settings.NEWSAPI_DOMAINS
            if domain_value:
                params["domains"] = domain_value
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.api_url, params=params)
                
                if resp.status_code != 200:
                    print(f"NewsAPI Error: {resp.status_code} {resp.text}")
                    return 0
                    
                data = resp.json()
                articles = data.get("articles", [])
                
                if not articles:
                    return 0
                    
                # Deduplication Logic
                urls = [item['url'] for item in articles]
                existing = db.query(News.url).filter(News.url.in_(urls)).all()
                existing_urls = set(row[0] for row in existing)
                
                new_items = []
                for item in articles:
                    if item['url'] not in existing_urls:
                        published_at = item.get("publishedAt")
                        try:
                            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00")) if published_at else datetime.utcnow()
                        except Exception:
                            published_at = datetime.utcnow()
                        news = News(
                            title=item['title'],
                            url=item['url'],
                            source=item['source']['name'],
                            published_at=published_at,
                            summary=item.get("description") or item.get("content") or ""
                        )
                        new_items.append(news)
                
                if new_items:
                    db.add_all(new_items)
                    db.commit()
                    print(f"Added {len(new_items)} new articles from NewsAPI.")
                    return len(new_items)
                
                return 0
                
        except Exception as e:
            print(f"Error fetching news: {e}")
            return 0
            
news_service = NewsService()
