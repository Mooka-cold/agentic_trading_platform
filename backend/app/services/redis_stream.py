import redis.asyncio as redis
import os
import json
import logging
from typing import AsyncGenerator

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0") # Default to Docker service name

logger = logging.getLogger("redis_stream")

class RedisStreamService:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)

    async def publish_message(self, channel: str, message: dict):
        try:
            await self.redis.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Redis Publish Error: {e}")

    async def subscribe_channel(self, channel: str) -> AsyncGenerator[str, None]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield message["data"]
        except Exception as e:
            logger.error(f"Redis Subscribe Error: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def set_cache(self, key: str, value: any, ttl: int = None):
        """Cache data with optional TTL"""
        try:
            val = json.dumps(value)
            await self.redis.set(key, val, ex=ttl)
        except Exception as e:
            logger.error(f"Redis Cache Set Error: {e}")

    async def get_cache(self, key: str) -> any:
        """Get cached data"""
        try:
            val = await self.redis.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.error(f"Redis Cache Get Error: {e}")
            return None

    async def close(self):
        await self.redis.close()

redis_stream = RedisStreamService()
