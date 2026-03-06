import httpx
import os
import asyncio
from typing import List, Dict, Optional

from sqlalchemy import create_engine, text
from core.config import settings

class SentimentService:
    def __init__(self):
        self.fear_greed_url = "https://api.alternative.me/fng/?limit=1"
        self.backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
        # Connect to User DB to fetch News (Fallback)
        self.engine = create_engine(settings.DATABASE_USER_URL)

    async def get_fear_greed_index(self) -> Dict:
        """
        Fetch Fear & Greed Index from Alternative.me
        Returns: {value: int, classification: str}
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.fear_greed_url)
                if resp.status_code == 200:
                    data = resp.json()
                    item = data['data'][0]
                    return {
                        "value": int(item['value']),
                        "classification": item['value_classification']
                    }
        except Exception as e:
            print(f"[Sentiment] Fear & Greed fetch failed: {e}")
        
        return {"value": 50, "classification": "Neutral"}

    async def get_latest_news(self, symbol: str = "BTC") -> List[Dict]:
        """
        Trigger Backend to fetch latest news, then read from DB.
        """
        # 1. Trigger Fetch
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{self.backend_url}/api/v1/news/fetch", params={"symbol": symbol})
        except Exception as e:
            print(f"[Sentiment] Warning: Failed to trigger news fetch: {e}")

        # 2. Read from DB
        query = text("""
            SELECT title, source, published_at, url, summary
            FROM news 
            ORDER BY published_at DESC 
            LIMIT 10
        """)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query).fetchall()
            
            if not result:
                return []

            # Parse votes from summary if possible, or mock
            # Our backend crawler stores votes string in summary: "Votes: +10/-2"
            # BUT NewsAPI stores actual description in summary.
            
            news_items = []
            for row in result:
                votes = {"positive": 0, "negative": 0}
                # If summary looks like votes, parse it (legacy CryptoPanic)
                if row.summary and "Votes:" in row.summary:
                    try:
                        parts = row.summary.replace("Votes: ", "").split("/")
                        if len(parts) == 2:
                            votes["positive"] = int(parts[0].replace("+", ""))
                            votes["negative"] = int(parts[1].replace("-", ""))
                    except:
                        pass
                
                news_items.append({
                    "title": row.title,
                    "source": row.source,
                    "published_at": str(row.published_at),
                    "domain": row.source, 
                    "url": row.url,
                    "votes": votes,
                    "summary": row.summary # Pass summary to Agent if needed
                })
            return news_items
            
        except Exception as e:
            print(f"[Sentiment] DB fetch failed: {e}")
            return []

    async def get_combined_sentiment(self, symbol: str) -> str:
        """
        Aggregates data for the Sentiment Agent.
        """
        fng = await self.get_fear_greed_index()
        news = await self.get_latest_news(symbol)
        
        # Format news objects into a string for the LLM
        news_str = "\n".join([
            f"- [{n['source']}] {n['title']} (Votes: +{n['votes'].get('positive',0)}/-{n['votes'].get('negative',0)})" 
            if isinstance(n, dict) else f"- {n}" 
            for n in news
        ])
        
        context = (
            f"Market Sentiment (Fear & Greed): {fng['value']} ({fng['classification']})\n"
            f"Latest News Headlines:\n{news_str}"
        )
        return context

sentiment_service = SentimentService()
