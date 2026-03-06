import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.crawler.news import NewsCrawler
from app.core.config import settings

async def test_sync():
    print(f"Testing CryptoPanic Fetcher...")
    print(f"API Key present: {bool(settings.CRYPTOPANIC_API_KEY)}")
    print(f"API Key value: {settings.CRYPTOPANIC_API_KEY[:5]}...")
    
    crawler = NewsCrawler()
    await crawler.fetch_cryptopanic()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(test_sync())
