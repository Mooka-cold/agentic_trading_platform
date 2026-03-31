import httpx
from shared.core.config import settings
import logging
from services.system_config import system_config_service
from model.policies import DataRoutingPolicy

logger = logging.getLogger(__name__)

class OnChainDataService:
    def __init__(self):
        self.backend_url = settings.BACKEND_URL
        self.crawler_url = settings.CRAWLER_URL
        
    async def get_onchain_metrics(self, symbol: str) -> dict:
        routing_policy = DataRoutingPolicy(**(system_config_service.get_json("DATA_ROUTING_POLICY") or {}))
        onchain_policy = routing_policy.onchain
        timeout_sec = max(1.0, float(onchain_policy.timeout_ms) / 1000.0)
        # Backend API for reading
        url = f"{self.backend_url}/api/v1/market/onchain/{symbol}"
        # Crawler API for triggering update
        trigger_url = f"{self.crawler_url}/api/v1/trigger/onchain"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=timeout_sec)
                if resp.status_code == 200:
                    data = resp.json()
                    
                    if not data:
                        logger.warning(f"OnChain data empty for {symbol}, triggering update...")
                        try:
                            await client.post(trigger_url, timeout=timeout_sec)
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
