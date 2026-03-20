import asyncio
import aiohttp
from typing import AsyncGenerator, List
from datetime import datetime
from app.core.interfaces import NewsSourceAdapter, NewsItem

class CryptoPanicFetcher(NewsSourceAdapter):
    BASE_URL = "https://cryptopanic.com/api/developer/v2/posts/"
    
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
        
        # Exponential backoff for 429
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.session.get(self.BASE_URL, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Debug: Print first item to understand structure
                        # if data.get("results"):
                        #    print(f"DEBUG FIRST ITEM: {data['results'][0]}")
                        
                        results = data.get("results", [])[:limit]
                        
                        for post in results:
                            # ... (Existing parsing logic)
                            try:
                                # Try standard format first
                                pub_date = datetime.strptime(post.get("published_at", ""), "%Y-%m-%dT%H:%M:%SZ")
                            except ValueError:
                                # Try ISO format with microseconds
                                try:
                                    pub_date = datetime.strptime(post.get("published_at", ""), "%Y-%m-%dT%H:%M:%S.%fZ")
                                except ValueError:
                                    pub_date = datetime.utcnow()
                            
                            # Handle URL
                            post_url = post.get("url")
                            if not post_url:
                                slug = post.get("slug")
                                if slug:
                                    post_url = f"https://cryptopanic.com/news/{post.get('id', '0')}/{slug}"
                                else:
                                    import hashlib
                                    title_hash = hashlib.md5(post.get("title", "").encode()).hexdigest()
                                    post_url = f"https://cryptopanic.com/news/hashed/{title_hash}"

                            yield NewsItem(
                                title=post.get("title", "No Title"),
                                summary=post.get("title", ""), 
                                url=post_url,
                                source=post.get("domain", "cryptopanic.com"),
                                timestamp=pub_date,
                                tags=[curr["code"] for curr in post.get("currencies", [])] if post.get("currencies") else []
                            )
                        break # Success, exit loop
                    elif response.status == 429:
                        print(f"⚠️ CryptoPanic Rate Limit (429). Retrying in {2**attempt}s...")
                        await asyncio.sleep(2**attempt)
                    else:
                        print(f"CryptoPanic API Error: {response.status}")
                        break
            except Exception as e:
                print(f"Error fetching news: {e}")
                await asyncio.sleep(1)

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
