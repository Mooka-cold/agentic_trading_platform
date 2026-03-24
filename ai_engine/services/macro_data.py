import httpx
from core.config import settings
import logging

logger = logging.getLogger(__name__)

class MacroDataService:
    def __init__(self):
        self.backend_url = settings.BACKEND_URL
        self.crawler_url = settings.CRAWLER_URL
        
    async def get_macro_metrics(self) -> dict:
        """
        Fetch latest macro metrics from Backend API.
        If data is stale or missing, trigger update via Crawler.
        """
        url = f"{self.backend_url}/api/v1/market/macro"
        trigger_url = f"{self.crawler_url}/api/v1/trigger/macro"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # Check freshness (simple check: if empty or no timestamp)
                    # Ideally backend handles staleness. 
                    # If empty, trigger update
                    if not data:
                        logger.warning("Macro data empty, triggering update...")
                        try:
                            await client.post(trigger_url, timeout=2.0)
                        except Exception as trigger_exc:
                            logger.warning(f"Macro trigger failed: {trigger_exc}")
                        return {}
                        
                    return data
                else:
                    logger.error(f"Failed to fetch macro metrics: {resp.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error connecting to Backend Macro API: {e}")
            return {}

macro_data_service = MacroDataService()
