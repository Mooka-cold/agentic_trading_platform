import feedparser
import asyncio
from datetime import datetime
from time import mktime
from sqlalchemy.orm import Session
from app.db.session import SessionLocalUser
from app.models.news import News
from app.services.news.sources.cryptopanic import CryptoPanicFetcher
from app.services.news_service import news_service
from app.core.config import settings

RSS_SOURCES = {
    "Cointelegraph": "https://cointelegraph.com/rss",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Bitcoin Magazine": "https://bitcoinmagazine.com/.rss/full/",
    "Decrypt": "https://decrypt.co/feed",
    "Chainalysis": "https://blog.chainalysis.com/feed/"
}

class NewsCrawler:
    def __init__(self):
        pass

    def fetch_rss(self, source_name: str, url: str):
        print(f"📰 Fetching news from {source_name}...")
        db = SessionLocalUser()
        try:
            feed = feedparser.parse(url)
            new_count = 0
            
            for entry in feed.entries[:10]: # Check last 10 entries
                # Check if exists
                exists = db.query(News).filter(News.url == entry.link).first()
                if exists:
                    continue
                
                # Parse date
                if hasattr(entry, 'published_parsed'):
                    dt = datetime.fromtimestamp(mktime(entry.published_parsed))
                else:
                    dt = datetime.utcnow()

                news_item = News(
                    title=entry.title,
                    summary=getattr(entry, 'summary', '')[:500], # Truncate summary
                    url=entry.link,
                    source=source_name,
                    published_at=dt,
                    sentiment="neutral" # Default
                )
                db.add(news_item)
                new_count += 1
            
            db.commit()
            if new_count > 0:
                print(f"✅ Saved {new_count} new articles from {source_name}")
                
        except Exception as e:
            print(f"❌ Error fetching {source_name}: {e}")
            db.rollback()
        finally:
            db.close()

    async def fetch_cryptopanic(self):
        if not settings.CRYPTOPANIC_API_KEY:
            print("⚠️ No CryptoPanic API Key found. Skipping.")
            return

        print(f"📰 Fetching news from CryptoPanic...")
        fetcher = CryptoPanicFetcher(api_key=settings.CRYPTOPANIC_API_KEY)
        await fetcher.connect()
        
        db = SessionLocalUser()
        new_count = 0
        try:
            async for item in fetcher.fetch_latest(limit=20):
                # Check if exists
                exists = db.query(News).filter(News.url == item.url).first()
                if exists:
                    continue
                
                news_item = News(
                    title=item.title,
                    summary=item.summary or item.title,
                    url=item.url,
                    source=f"CryptoPanic-{item.source}", # Add source info clearly
                    published_at=item.timestamp,
                    sentiment="neutral"
                )
                db.add(news_item)
                new_count += 1
            
            db.commit()
            if new_count > 0:
                print(f"✅ Saved {new_count} new articles from CryptoPanic")
        except Exception as e:
            print(f"❌ Error fetching CryptoPanic: {e}")
            db.rollback()
        finally:
            db.close()
            await fetcher.disconnect()

    async def fetch_newsapi(self):
        db = SessionLocalUser()
        try:
            await news_service.fetch_and_store_news(
                db,
                symbol="BTC/USDT",
                query=settings.NEWSAPI_QUERY or None,
                domains=settings.NEWSAPI_DOMAINS or None,
                page_size=50
            )
        finally:
            db.close()

    async def sync_news(self):
        """
        Sync news from all sources.
        """
        loop = asyncio.get_event_loop()
        
        # 1. Fetch RSS (Thread Pool)
        for name, url in RSS_SOURCES.items():
            await loop.run_in_executor(None, self.fetch_rss, name, url)
            
        # 2. Fetch CryptoPanic (Async)
        await self.fetch_cryptopanic()
        await self.fetch_newsapi()

    def close(self):
        pass
