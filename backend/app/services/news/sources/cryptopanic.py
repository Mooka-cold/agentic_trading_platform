import asyncio
import aiohttp
from typing import AsyncGenerator, List
from datetime import datetime
from app.core.interfaces import NewsSourceAdapter, NewsItem

class CryptoPanicFetcher(NewsSourceAdapter):
    BASE_URL = "https://cryptopanic.com/api/v1/posts/"
    
    def __init__(self, api_key: str, currencies: str = "BTC,ETH"):
        self.api_key = api_key
        self.currencies = currencies
        self.session = None

    async def connect(self):
        self.session = aiohttp.ClientSession()
        print(f"Connected to CryptoPanic API")

    async def fetch_latest(self, limit: int = 20) -> AsyncGenerator[NewsItem, None]:
        if not self.session:
            await self.connect()
            
        params = {
            "auth_token": self.api_key,
            "currencies": self.currencies,
            "kind": "news",
            "filter": "important",
            "public": "true"
        }
        
        try:
            async with self.session.get(self.BASE_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])[:limit]
                    
                    for post in results:
                        # Parse date string to datetime
                        # Format: "2023-10-27T10:00:00Z"
                        pub_date = datetime.strptime(post["published_at"], "%Y-%m-%dT%H:%M:%SZ")
                        
                        yield NewsItem(
                            title=post["title"],
                            summary=post["title"], # CryptoPanic often has title as summary
                            url=post["url"],
                            source=post["domain"],
                            timestamp=pub_date,
                            tags=[curr["code"] for curr in post.get("currencies", [])]
                        )
                else:
                    print(f"CryptoPanic API Error: {response.status}")
        except Exception as e:
            print(f"Error fetching news: {e}")

    async def listen(self) -> AsyncGenerator[NewsItem, None]:
        """
        Polling implementation for real-time news
        """
        while True:
            async for item in self.fetch_latest(limit=5):
                yield item
            # Poll every 5 minutes to respect rate limits
            await asyncio.sleep(300)

    async def disconnect(self):
        if self.session:
            await self.session.close()
