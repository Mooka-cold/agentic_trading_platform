import asyncio
from datetime import datetime, timedelta
from html import unescape
from time import mktime
import hashlib
import re

import feedparser
import httpx

from shared.core.config import settings
from shared.db.session import SessionLocalUser
from shared.models.news import News


RSS_SOURCES = {
    "Cointelegraph": "https://cointelegraph.com/rss",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Bitcoin Magazine": "https://bitcoinmagazine.com/.rss/full/",
    "Decrypt": "https://decrypt.co/feed",
    "Chainalysis": "https://blog.chainalysis.com/feed/",
}

TECHFLOW_SOURCES = [
    ("TechFlow-Newsletter", "https://www.techflowpost.com/zh-CN/newsletter?articleType=0"),
    ("TechFlow-OnchainWhale", "https://www.techflowpost.com/zh-CN/newsletter?articleType=1001"),
]


class NewsCrawler:
    def _run_rss_sync_sync(self, name: str, url: str):
        db = SessionLocalUser()
        try:
            feed = feedparser.parse(url)
            new_count = 0
            for entry in feed.entries[:10]:
                link = getattr(entry, "link", "")
                if not link:
                    continue
                if db.query(News).filter(News.url == link).first():
                    continue
                dt = datetime.utcnow()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    dt = datetime.fromtimestamp(mktime(entry.published_parsed))
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                summary = re.sub("<[^<]+?>", "", summary)[:500]
                db.add(
                    News(
                        title=getattr(entry, "title", "No Title"),
                        summary=summary,
                        url=link,
                        source=name,
                        published_at=dt,
                        sentiment="neutral",
                    )
                )
                new_count += 1
            if new_count > 0:
                db.commit()
        except Exception as exc:
            print(f"RSS sync failed for {name}: {exc}")
            db.rollback()
        finally:
            db.close()

    async def sync_rss(self):
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, self._run_rss_sync_sync, name, url) for name, url in RSS_SOURCES.items()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def sync_newsapi(self):
        if not settings.NEWS_API_KEY:
            return
        query_keyword = settings.NEWSAPI_QUERY or "bitcoin OR crypto OR ethereum"
        params = {
            "q": query_keyword,
            "searchIn": "title,description",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 50,
            "apiKey": settings.NEWS_API_KEY,
        }
        if settings.NEWSAPI_DOMAINS:
            params["domains"] = settings.NEWSAPI_DOMAINS
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get("https://newsapi.org/v2/everything", params=params)
            if resp.status_code != 200:
                print(f"NewsAPI error: {resp.status_code} {resp.text}")
                return
            articles = (resp.json() or {}).get("articles", [])
        db = SessionLocalUser()
        try:
            urls = [item.get("url") for item in articles if item.get("url")]
            existing = db.query(News.url).filter(News.url.in_(urls)).all() if urls else []
            existing_urls = {row[0] for row in existing}
            for item in articles:
                url = item.get("url")
                if not url or url in existing_urls:
                    continue
                published_at = item.get("publishedAt")
                try:
                    published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00")) if published_at else datetime.utcnow()
                except Exception:
                    published_at = datetime.utcnow()
                db.add(
                    News(
                        title=item.get("title") or "No Title",
                        summary=item.get("description") or item.get("content") or "",
                        url=url,
                        source=((item.get("source") or {}).get("name") or "NewsAPI"),
                        published_at=published_at,
                        sentiment="neutral",
                    )
                )
            db.commit()
        except Exception as exc:
            print(f"NewsAPI persistence failed: {exc}")
            db.rollback()
        finally:
            db.close()

    async def sync_cryptopanic(self):
        if not settings.CRYPTOPANIC_API_KEY:
            return
        params = {
            "auth_token": settings.CRYPTOPANIC_API_KEY,
            "currencies": "BTC,ETH,SOL,BNB,XRP",
            "kind": "news",
            "filter": "important",
            "public": "true",
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get("https://cryptopanic.com/api/developer/v2/posts/", params=params)
            if resp.status_code != 200:
                print(f"CryptoPanic error: {resp.status_code} {resp.text}")
                return
            items = ((resp.json() or {}).get("results") or [])[:20]
        db = SessionLocalUser()
        try:
            for post in items:
                title = post.get("title") or "No Title"
                source = post.get("domain") or "cryptopanic.com"
                post_url = post.get("url")
                if not post_url:
                    slug = post.get("slug")
                    post_id = post.get("id", "0")
                    post_url = f"https://cryptopanic.com/news/{post_id}/{slug}" if slug else f"https://cryptopanic.com/news/hashed/{hashlib.md5(title.encode()).hexdigest()}"
                if db.query(News).filter(News.url == post_url).first():
                    continue
                ts_raw = post.get("published_at") or ""
                published_at = datetime.utcnow()
                for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
                    try:
                        published_at = datetime.strptime(ts_raw, fmt)
                        break
                    except Exception:
                        pass
                db.add(
                    News(
                        title=title,
                        summary=title,
                        url=post_url,
                        source=f"CryptoPanic-{source}",
                        published_at=published_at,
                        sentiment="neutral",
                    )
                )
            db.commit()
        except Exception as exc:
            print(f"CryptoPanic persistence failed: {exc}")
            db.rollback()
        finally:
            db.close()

    async def _fetch_text_with_retry(self, url: str, retries: int = 3, timeout_seconds: float = 10.0) -> str:
        last_error = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(min(2**attempt, 5))
        raise RuntimeError(f"Failed to fetch {url}: {last_error}")

    def _normalize_techflow_text(self, html_text: str) -> str:
        content = re.sub(r"<script[^>]*>.*?</script>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r"<style[^>]*>.*?</style>", " ", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r"<[^>]+>", " ", content)
        content = unescape(content).replace("\u200b", "").replace("​​", "")
        return re.sub(r"\s+", " ", content).strip()

    def _parse_techflow_items(self, source_name: str, text: str):
        now = datetime.utcnow()
        pattern = re.compile(r"(?P<time>\d{1,2}/\d{1,2}\s\d{2}:\d{2})(?P<body>.*?)(?=(?:\d{1,2}/\d{1,2}\s\d{2}:\d{2})|$)")
        items = []
        for match in pattern.finditer(text):
            time_token = match.group("time").strip()
            body = match.group("body").strip()
            if not body:
                continue
            split_idx = body.find("据")
            title = body[:split_idx].strip() if split_idx > 0 else body
            title = title.replace("[原文链接]", "").strip()
            if len(title) < 6:
                continue
            summary = body.replace("[原文链接]", "").strip()[:500]
            try:
                month_day, hhmm = time_token.split(" ")
                month, day = month_day.split("/")
                hour, minute = hhmm.split(":")
                published_at = datetime(now.year, int(month), int(day), int(hour), int(minute))
                if published_at > now + timedelta(days=1):
                    published_at = published_at.replace(year=now.year - 1)
            except Exception:
                published_at = now
            dedup_hash = hashlib.md5(f"{source_name}|{title}|{time_token}".encode("utf-8")).hexdigest()
            items.append(
                {
                    "title": title,
                    "summary": summary,
                    "url": f"techflow://item-{dedup_hash}",
                    "source": source_name,
                    "published_at": published_at,
                }
            )
        return items

    async def fetch_techflow_news(self):
        total = 0
        db = SessionLocalUser()
        try:
            for source_name, page_url in TECHFLOW_SOURCES:
                html_text = await self._fetch_text_with_retry(page_url, retries=3, timeout_seconds=10.0)
                parsed_items = self._parse_techflow_items(source_name, self._normalize_techflow_text(html_text))
                existing_rows = db.query(News.title, News.published_at).filter(News.source == source_name).all()
                # Use a helper function or pre-calculate to avoid backslash in f-string expression
                def clean_title(title_str):
                    return re.sub(r'\s+', ' ', title_str).strip()
                
                existing_keys = {f"{source_name}|{clean_title(row[0])}|{row[1].strftime('%Y-%m-%d %H:%M')}" for row in existing_rows}
                for item in parsed_items:
                    key = f"{source_name}|{clean_title(item['title'])}|{item['published_at'].strftime('%Y-%m-%d %H:%M')}"
                    if key in existing_keys:
                        continue
                    db.add(
                        News(
                            title=item["title"],
                            summary=item["summary"],
                            url=item["url"],
                            source=item["source"],
                            published_at=item["published_at"],
                            sentiment="neutral",
                        )
                    )
                    total += 1
            if total > 0:
                db.commit()
        except Exception as exc:
            print(f"TechFlow sync failed: {exc}")
            db.rollback()
        finally:
            db.close()
        return total

    async def sync_news(self):
        await self.sync_rss()
        await self.sync_newsapi()
