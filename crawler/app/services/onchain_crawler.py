import requests
from datetime import datetime
from sqlalchemy.orm import Session
from shared.models.onchain import OnChainMetric
import logging

logger = logging.getLogger(__name__)

class OnChainCrawlerService:
    def __init__(self, db: Session):
        self.db = db
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }

    def fetch_and_store_all(self):
        logger.info("Starting On-Chain Data Update...")
        self._fetch_oi("BTC")
        self._fetch_ls_ratio("BTC")
        self.db.commit()
        logger.info("On-Chain Update Complete.")

    def _fetch_oi(self, symbol):
        try:
            # Using Coinglass public API (This might fail due to WAF or Endpoint deprecation)
            # Update to newer endpoint if available
            url = f"https://fapi.coinglass.com/api/futures/openInterest/chart?symbol={symbol}&interval=1h"
            res = requests.get(url, headers=self.headers, timeout=5)
            
            if res.status_code == 200 and res.json().get("code") == "0":
                data_list = res.json().get("data", {}).get("dataMap", {}).get("Binance", [])
                if data_list:
                    latest_oi = data_list[-1]
                    self._upsert_metric(f"{symbol}_OI", symbol, "OI", latest_oi, "USD")
                    return
            else:
                logger.warning(f"Coinglass OI API failed or 404 for {symbol}")
                
        except Exception as e:
            logger.error(f"Failed to fetch OI for {symbol}: {e}")

    def _fetch_ls_ratio(self, symbol):
        try:
            # Long/Short Ratio (Global)
            url = f"https://fapi.coinglass.com/api/futures/longShortRate?symbol={symbol}&timeType=1"
            res = requests.get(url, headers=self.headers, timeout=5)
            
            if res.status_code == 200 and res.json().get("code") == "0":
                data_list = res.json().get("data", [])
                if data_list:
                    # Just take Binance or global avg
                    for item in data_list:
                        if item.get("exchangeName") == "Binance":
                            ls_ratio = item.get("longShortRatio")
                            if ls_ratio:
                                self._upsert_metric(f"{symbol}_LS_RATIO", symbol, "LS_RATIO", ls_ratio, "Ratio")
                                return
            else:
                logger.warning(f"Coinglass LS API failed or 404 for {symbol}")
                
        except Exception as e:
            logger.error(f"Failed to fetch LS Ratio for {symbol}: {e}")

    def _upsert_metric(self, uid, symbol, name, value, unit):
        obj = self.db.query(OnChainMetric).filter(OnChainMetric.id == uid).first()
        if not obj:
            obj = OnChainMetric(id=uid, symbol=symbol, metric_name=name)
            self.db.add(obj)
        
        obj.value = value
        obj.unit = unit
        obj.timestamp = datetime.utcnow()
