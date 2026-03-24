import httpx
from shared.core.config import settings
import logging

logger = logging.getLogger(__name__)

class OnChainDataService:
    def __init__(self):
        self.backend_url = settings.BACKEND_URL
        self.crawler_url = settings.CRAWLER_URL
        
    async def get_onchain_metrics(self, symbol: str) -> dict:
        # Backend API for reading
        url = f"{self.backend_url}/api/v1/market/onchain/{symbol}"
        # Crawler API for triggering update
        trigger_url = f"{self.crawler_url}/api/v1/trigger/onchain"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    
                    if not data:
                        logger.warning(f"OnChain data empty for {symbol}, triggering update...")
                        try:
                            await client.post(trigger_url, timeout=2.0)
                        except Exception as trigger_exc:
                            logger.warning(f"OnChain trigger failed for {symbol}: {trigger_exc}")
                        return {}
                        
                    return data
                else:
                    logger.error(f"Failed to fetch onchain metrics: {resp.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error connecting to Backend OnChain API: {e}")
            return {}

onchain_data_service = OnChainDataService()
